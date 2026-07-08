#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Định nghĩa các chế độ chạy (Modes)
MODE_ASSIGN_MASTER   = "1. Auto Assign Master View"
MODE_CHANGE_POINT    = "2. Change Point"
MODE_3D_ANNO_REVIEW  = "3. Auto Assign 3D Anno/Review (Limit)"
MODE_INSPECTION_AI   = "4. Auto Assign Inspection AI"
MODE_IMPORT_2D       = "5. Auto Import & Reopen Task 2D"
MODE_IMPORT_3D       = "6. Auto Import & Reopen Task 3D"
MODE_STATUS_SET      = "7. Auto Status Set (Open Step)"

st.set_page_config(page_title="AI Studio Automation Suite", layout="wide")
st.title("🤖 AI Studio Automation Suite - Render Web Edition")

# --- GIAO DIỆN CẤU HÌNH TRÊN WEB ---
col_left, col_right = st.columns([2, 1])

with col_left:
    project_url = st.text_input("1. Nhập URL Dự án (Project URL):", "https://www.ai-studio.co.kr/po/task/taskList?projectId=")
    uploaded_file = st.file_uploader("2. Tải lên File chứa danh sách Task (.txt):", type=["txt"])
    mode = st.selectbox("3. Lựa chọn chức năng Script muốn chạy:", [
        MODE_ASSIGN_MASTER, MODE_CHANGE_POINT, MODE_3D_ANNO_REVIEW, 
        MODE_INSPECTION_AI, MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET
    ])

with col_right:
    st.info("💡 **Quy trình vận hành:**\n1. Điền URL dự án.\n2. Upload file txt.\n3. Chọn chức năng và bấm nút kích hoạt.\n*Hệ thống sử dụng Session Profile đã nạp sẵn để vượt OTP ngầm.*")
    with st.expander("📄 Hướng dẫn file mẫu (.txt)"):
        if mode == MODE_CHANGE_POINT:
            st.code("task_name\tanno_point\trv_point\nPCD_Slot_01\t15\t5", language="text")
        elif mode == MODE_3D_ANNO_REVIEW:
            st.code("task_name\tworker_id\treviewer_id\tlimit\nPCD_Box_01\tworker_thai\treviewer_an\t50\nPCD_Box_02\t-\treviewer_an\t100", language="text")
        elif mode == MODE_STATUS_SET:
            st.code("task_name\tstatus_value\n2D_Retouch_001\tSTEP02", language="text")
        else:
            st.code("task_name\tgiá_trị_cột_2\nTask_Name_01\tID_hoặc_Tên_File", language="text")

# --- LỚP AUTOMATION CHẠY TRÊN RENDER ---
class RenderAutomation:
    def __init__(self, p_url, file_content, run_mode, log_callback):
        self.project_url = p_url
        self.file_content = file_content
        self.mode = run_mode
        self.log_callback = log_callback
        self.driver = None

    def create_driver(self):
        options = webdriver.ChromeOptions()
        # CẤU HÌNH BẮT BUỘC TRÊN SERVER RENDER
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--force-device-scale-factor=0.67")
        
        # Cấu hình tab chạy nền ổn định trên Linux
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-background-timer-throttling")

        # Nạp Chrome Profile đã đăng nhập sẵn từ thư mục dự án
        profile_path = os.path.join(os.getcwd(), "chrome_user_data")
        options.add_argument(f"--user-data-dir={profile_path}")

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(120)

    def wait_loading(self):
        try:
            loading = WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".loading-wrap")))
            WebDriverWait(self.driver, 60).until(lambda d: "on" not in (loading.get_attribute("class") or ""))
        except Exception: pass

    def accept_alert_if_present(self, timeout=2, label="alert"):
        try:
            WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
            alert = self.driver.switch_to.alert
            text = alert.text
            alert.accept()
            time.sleep(0.4)
            return text
        except Exception: return None

    def robust_click(self, elem, name="element"):
        for fn in (lambda: elem.click(), lambda: self.driver.execute_script("arguments[0].click();", elem)):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
                time.sleep(0.2)
                fn()
                return
            except Exception: time.sleep(0.2)
        raise Exception(f"Failed to click {name}")

    def js_set_value(self, elem, value):
        self.driver.execute_script(
            "arguments[0].focus(); arguments[0].value = '';"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", elem, str(value)
        )

    def open_search_form_if_needed(self):
        self.accept_alert_if_present(timeout=0.2, label="before search")
        search_frm = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchFrm")))
        if "open" not in (search_frm.get_attribute("class") or ""):
            toggle_btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick*='searchFrm']")))
            self.robust_click(toggle_btn, "search form toggle")
            WebDriverWait(self.driver, 3).until(lambda d: "open" in (search_frm.get_attribute("class") or ""))

    def input_task_name(self, task_name):
        search_input = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchVal")))
        self.robust_click(search_input, "Task Search Input")
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        search_input.clear()
        search_input.send_keys(task_name)
        time.sleep(0.2)

    def find_matching_row(self, task_name):
        rows = self.driver.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        for row in rows:
            try:
                txt = " | ".join(td.text.strip() for td in row.find_elements(By.TAG_NAME, "td"))
                if task_name in txt: return row
            except Exception: continue
        return None

    def click_task_name_from_row(self, row, task_name):
        tds = row.find_elements(By.TAG_NAME, "td")
        task_name_cell = tds[1]
        anchors = task_name_cell.find_elements(By.TAG_NAME, "a")
        if anchors:
            self.robust_click(anchors[0], "task name anchor")
            return
        spans = task_name_cell.find_elements(By.CSS_SELECTOR, "span.ellipsis.underline")
        if spans:
            self.robust_click(spans[0], "task name span")
            return
        self.robust_click(task_name_cell, "task name cell")

    def open_member_tab(self):
        member_tab = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member'] | //button[normalize-space()='Member']")))
        self.robust_click(member_tab, "Member tab")

    def assign_member_popup_core(self, member_id, search_onclick_btn, row_checkbox_selector):
        search_input = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
        self.robust_click(search_input, "popup search input")
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        self.js_set_value(search_input, member_id)
        time.sleep(0.3)
        search_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, search_onclick_btn)))
        self.robust_click(search_btn, "popup search button")
        time.sleep(1)
        checkbox = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, row_checkbox_selector)))
        self.driver.execute_script("arguments[0].checked = true;", checkbox)
        self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", checkbox)
        time.sleep(0.3)
        popup_save_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[@onclick='addMemberSearchMember()']")))
        self.robust_click(popup_save_btn, "popup save button")
        time.sleep(0.5)

    def click_final_save(self):
        final_save_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[@onclick='updateAssignCnt()']")))
        self.robust_click(final_save_btn, "final save button")
        time.sleep(0.5)
        self.accept_alert_if_present(timeout=5, label="task saved alert")

    def process_import_and_reopen_core(self, item, li_index_selector):
        self.open_search_form_if_needed()
        self.input_task_name(item["task_name"])
        self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); self.wait_loading()
        toggle_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#task_list > tr:nth-child(1) button[onclick*='utils.fn.layer.toggle']")))
        self.robust_click(toggle_btn, "Layer Toggle"); time.sleep(0.3)
        import_link = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"#task_list > tr:nth-child(1) > td:nth-child(10) ul li:nth-child({li_index_selector}) > a")))
        self.robust_click(import_link, f"Go Import URL (li {li_index_selector})")
        WebDriverWait(self.driver, 60).until(lambda d: "importTask" in d.current_url); self.wait_loading()
        self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "label[for=\"txtImportFileName\"]"), "Open zTree popup")
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#zTree")))
        tree_items = self.driver.find_elements(By.CSS_SELECTOR, "#zTree a")
        target = None
        import_file_norm = item["col2"].strip()
        for a in tree_items:
            if (a.text or "").strip() == import_file_norm: target = a; break
        if target is None:
            for a in tree_items:
                if import_file_norm in (a.text or "").strip(): target = a; break
        if target is None: raise Exception(f"Không thấy file: {import_file_norm} trên zTree")
        self.robust_click(target, "Select file")
        btn_upload = WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn_upload")))
        btn_upload.click()
        while True:
            try: WebDriverWait(self.driver, 2).until(EC.alert_is_present()); self.driver.switch_to.alert.accept()
            except Exception: break
        self.wait_loading()
        self.driver.get(self.project_url); self.wait_loading()
        self.open_search_form_if_needed()
        self.input_task_name(item["task_name"])
        self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); self.wait_loading()
        self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1) span.ellipsis.underline"), "Task Link"); self.wait_loading()
        reopen_btns = self.driver.find_elements(By.CSS_SELECTOR, "#taskReOpen")
        if reopen_btns:
            self.robust_click(reopen_btns[0], "ReOpen")
            while True:
                try: WebDriverWait(self.driver, 2).until(EC.alert_is_present()); self.driver.switch_to.alert.accept()
                except Exception: break
            self.wait_loading()

    def execute_mode_logic(self, item):
        self.driver.get(self.project_url)
        self.wait_loading()
        self.accept_alert_if_present(timeout=1, label="init URL")

        if self.mode == MODE_IMPORT_2D: self.process_import_and_reopen_core(item, 6)
        elif self.mode == MODE_IMPORT_3D: self.process_import_and_reopen_core(item, 5)
        elif self.mode == MODE_STATUS_SET:
            self.open_search_form_if_needed()
            self.input_task_name(item["task_name"])
            self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); self.wait_loading()
            toggle_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#task_list > tr:nth-child(1) button[onclick*='utils.fn.layer.toggle']")))
            self.robust_click(toggle_btn, "Layer Toggle")
            status_link = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#task_list > tr:nth-child(1) > td:nth-child(10) div.div-pop ul li:nth-child(3) > a")))
            self.robust_click(status_link, "Go Status Set"); self.wait_loading()
            radio_open = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='radioOpen']")))
            self.robust_click(radio_open, "Radio Open")
            from selenium.webdriver.support.ui import Select
            el = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#openSelect")))
            if el.get_attribute("disabled") is None:
                Select(el).select_by_value(str(item["col2"]))
                save_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick='fnTaskStatusSet()']")))
                self.robust_click(save_btn, "Save")
                while True:
                    try: WebDriverWait(self.driver, 2).until(EC.alert_is_present()); self.driver.switch_to.alert.accept()
                    except Exception: break
                self.wait_loading()
        elif self.mode == MODE_ASSIGN_MASTER:
            completed_tab = WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Completed Tasks']")))
            self.robust_click(completed_tab, "Completed Tasks tab"); self.wait_loading()
            self.open_search_form_if_needed()
            self.input_task_name(item["task_name"])
            self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); self.wait_loading()
            row = self.find_matching_row(item["task_name"])
            if not row: raise Exception("Not found in Completed")
            self.click_task_name_from_row(row, item["task_name"]); self.wait_loading()
            self.open_member_tab()
            add_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-member.add[onclick='searchMemberList(3)']")))
            self.robust_click(add_btn, "Add Master")
            self.assign_member_popup_core(item["col2"], "//button[@onclick='searchMember()']", "#memberList input.memberChk")
            self.accept_alert_if_present(timeout=3, label="Master alert")
            self.click_final_save()
        elif self.mode == MODE_CHANGE_POINT:
            self.open_search_form_if_needed()
            self.input_task_name(item["task_name"])
            self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); self.wait_loading()
            row = self.find_matching_row(item["task_name"])
            if not row: raise Exception("Task not found")
            self.click_task_name_from_row(row, item["task_name"]); self.wait_loading()
            alter_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-s-point")))
            self.robust_click(alter_btn, "open point popup"); time.sleep(0.5)
            for key, val in [("#updateWorkPoint", item["anno_point"]), ("#updateReviewPoint", item["rv_point"])]:
                inp = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, key)))
                inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(val))
            confirm_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-l-point")))
            self.robust_click(confirm_btn, "Confirm"); self.wait_loading()
        elif self.mode == MODE_3D_ANNO_REVIEW:
            progress_tab = WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.XPATH, "//li[@onclick='ingtask()']")))
            self.robust_click(progress_tab, "In-progress Tasks tab"); self.wait_loading()
            self.open_search_form_if_needed()
            self.input_task_name(item["task_name"])
            self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); self.wait_loading()
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#task_list > tr")))
            if "no data" in self.driver.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1)").text.lower(): raise Exception("No match task")
            task_span = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#task_list > tr:nth-child(1) span.ellipsis.underline")))
            self.robust_click(task_span, "First task"); self.wait_loading()
            self.open_member_tab()
            if item["worker_id"] and item["worker_id"].strip() not in ("-", "none", "None"):
                worker_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button#button_WorkMember.btn-member.add[onclick*='searchMemberList(0)']")))
                self.robust_click(worker_btn, "Worker Popup")
                self.assign_member_popup_core(item["worker_id"], "//button[@onclick='searchMember()']", "#memberList input.memberChk")
            if item["anno_limit"]:
                inp = WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#workAssignCnt")))
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
                inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(item["anno_limit"]))
            if item["reviewer_id"]:
                rev_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-member.add[onclick*='searchMemberList(1)']")))
                self.robust_click(rev_btn, "Reviewer Popup")
                self.assign_member_popup_core(item["reviewer_id"], "//button[@onclick='searchMember()']", "#memberList input.memberChk")
                self.accept_alert_if_present(timeout=3, label="Reviewer alert")
            self.click_final_save()
        elif self.mode == MODE_INSPECTION_AI:
            self.open_search_form_if_needed()
            self.input_task_name(item["task_name"])
            self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); self.wait_loading()
            row = self.find_matching_row(item["task_name"])
            if row is None:
                completed_tab = WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.XPATH, "//li[contains(., 'Completed Tasks')]")))
                self.robust_click(completed_tab, "Completed Tasks"); self.wait_loading()
                self.open_search_form_if_needed(); self.input_task_name(item["task_name"])
                self.robust_click(self.driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); self.wait_loading()
                row = self.find_matching_row(item["task_name"])
            if row is None: raise Exception("Inspector task not found")
            self.click_task_name_from_row(row, item["task_name"]); self.wait_loading()
            self.open_member_tab()
            role_title = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Inspector']")))
            current = role_title; panel = None
            for _ in range(8):
                current = current.find_element(By.XPATH, "./..")
                if "Inspector" in current.text and "Persons" in current.text: panel = current; break
            if panel is None: raise Exception("Inspector panel not found")
            add_btn = panel.find_element(By.CSS_SELECTOR, "button.btn-member.add")
            self.robust_click(add_btn, "Add Inspector")
            self.assign_member_popup_core(item["col2"], "//button[contains(., 'Search')]", "input.memberChk")
            self.accept_alert_if_present(timeout=3, label="Inspector alert")
            self.click_final_save()

    def parse_uploaded_file(self):
        tasks = []
        lines = self.file_content.decode("utf-8-sig").splitlines()
        for line_no, line in enumerate(lines, start=1):
            raw = line.strip()
            if not raw or raw.startswith("#"): continue
            parts = raw.split("\t") if "\t" in raw else (raw.split(",") if "," in raw else raw.split())
            if len(parts) < 2: continue
            
            task_name, col2 = parts[0], parts[1]
            anno_point, rv_point = "0", "0"
            worker_id, reviewer_id, anno_limit = None, None, None
            
            if len(parts) == 2: worker_id = parts[1]
            else:
                if parts[1].isdigit() and parts[2].isdigit(): anno_point, rv_point = parts[1], parts[2]
                else:
                    worker_id = parts[1]
                    if len(parts) >= 3:
                        if parts[2].isdigit(): anno_limit = parts[2]
                        else: reviewer_id = parts[2]
                    if len(parts) >= 4 and parts[3].isdigit(): anno_limit = parts[3]

            tasks.append({
                "line_no": line_no, "task_name": task_name, "col2": col2,
                "anno_point": anno_point, "rv_point": rv_point,
                "worker_id": worker_id, "reviewer_id": reviewer_id, "anno_limit": anno_limit
            })
        return tasks

    def start(self):
        try:
            tasks = self.parse_uploaded_file()
            if not tasks: st.error("Không tìm thấy hàng dữ liệu hợp lệ."); return
            
            st.info(f"🚀 Nạp thành công {len(tasks)} task. Đang khởi tạo trình duyệt Selenium ẩn ngầm...")
            self.create_driver()
            
            # Kiểm tra nhanh trạng thái Cookies của Profile
            self.driver.get(self.project_url); time.sleep(2)
            if "/login" in self.driver.current_url:
                st.error("❌ Lỗi: Cookies hết hạn hoặc thư mục `chrome_user_data` trống. Hãy làm lại Bước 1 đăng nhập trên máy cá nhân rồi nén tải lên lại.")
                return

            progress_bar = st.progress(0)
            log_container = st.empty()
            logs = []

            for idx, item in enumerate(tasks, start=1):
                try:
                    self.execute_mode_logic(item)
                    msg = f"🟢 Dòng {item['line_no']} | Thành công | Task: {item['task_name']}"
                except Exception as e:
                    msg = f"🔴 Dòng {item['line_no']} | Lỗi: {str(e).splitlines()[0]} | Task: {item['task_name']}"
                logs.append(msg)
                log_container.code("\n".join(logs))
                progress_bar.progress(idx / len(tasks))
                
            st.success("🎉 Đã hoàn thành toàn bộ file danh sách nhiệm vụ!")
        except Exception as global_err:
            st.error(f"💥 Lỗi hệ thống phát sinh: {global_err}")
        finally:
            if self.driver: self.driver.quit()

# Nút trigger hoạt động
if st.button("KÍCH HOẠT CHẠY TỰ ĐỘNG", type="primary"):
    if not uploaded_file: st.warning("Vui lòng tải file cấu hình .txt lên trước!")
    elif "projectId=" not in project_url: st.warning("Vui lòng nhập link Project URL hợp lệ!")
    else:
        runner = RenderAutomation(project_url, uploaded_file.read(), mode, st.text)
        runner.start()