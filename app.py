#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import traceback
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
st.title("🤖 AI Studio Automation Suite - Cookie Bypass Edition")

# --- GIAO DIỆN CẤU HÌNH HAI CỘT ---
col_left, col_right = st.columns([2, 1])

with col_left:
    project_url = st.text_input("1. Nhập URL Dự án (Project URL):", "https://www.ai-studio.co.kr/po/task/taskList?projectId=")
    uploaded_file = st.file_uploader("2. Tải lên File chứa danh sách Task (.txt):", type=["txt"])
    mode = st.selectbox("3. Lựa chọn chức năng Script muốn chạy:", [
        MODE_ASSIGN_MASTER, MODE_CHANGE_POINT, MODE_3D_ANNO_REVIEW, 
        MODE_INSPECTION_AI, MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET
    ])
    
    # 🔑 Ô dán Cookies thông minh - Giải quyết triệt để vấn đề Authenticator OTP
    cookie_raw = st.text_area("4. Dán chuỗi Cookies của bạn vào đây (Đã sao chép từ Cookie-Editor dưới dạng JSON):", height=150, 
                              placeholder='[{"name": "JSESSIONID", "value": "..."}, ...]')

# --- KHÔI PHỤC HOÀN TOÀN KHỐI HƯỚNG DẪN VÀ FILE CẤU TRÚC MẪU PHÍA PHẢI ---
with col_right:
    st.info("💡 **Hướng dẫn lấy Cookie nhanh cho Worker:**\n1. Đăng nhập vào `ai-studio.co.kr` trên trình duyệt Chrome máy cá nhân.\n2. Cài extension **Cookie-Editor**.\n3. Bấm vào icon extension $\rightarrow$ Chọn **Export** $\rightarrow$ Chọn định dạng **JSON**.\n4. Dán toàn bộ chuỗi text vừa copy vào ô bên cạnh rồi bấm chạy.")
    
    st.markdown("### 📋 Hướng dẫn file cấu hình mẫu (.txt)")
    with st.expander("📄 Xem cấu trúc chuẩn theo chức năng đang chọn", expanded=True):
        if mode == MODE_ASSIGN_MASTER:
            st.markdown("**Chức năng:** Tự động gán tài khoản vai trò Master View (Tab Completed).")
            st.markdown("**Cấu trúc:** 2 cột (Tên task + ID Master)")
            st.code("2D_TLD_Pack006_001\tmaster_thai_01\n2D_TLD_Pack006_002\tmaster_thai_01", language="text")
            
        elif mode == MODE_CHANGE_POINT:
            st.markdown("**Chức năng:** Thay đổi nhanh điểm số Anno Point và Review Point.")
            st.markdown("**Cấu trúc:** 3 cột (Tên task + Điểm Anno + Điểm Review)")
            st.code("PCD_Parking_Slot_01\t15\t5\nPCD_Parking_Slot_02\t20\t10", language="text")
            
        elif mode == MODE_3D_ANNO_REVIEW:
            st.markdown("**Chức năng:** Gán Worker, Reviewer và đặt giới hạn ảnh chạy liên tục (Limit).")
            st.markdown("**Cấu trúc động:** Tùy chọn 2 đến 4 cột. Nếu muốn bỏ qua Worker để gán thẳng Review+Limit, hãy điền dấu `-` hoặc chữ `none` vào cột Worker.")
            st.code("# Dạng đủ: Name, Worker, Reviewer, Limit\nPCD_Slot_Box_001\tworker_thai\treviewer_an\t50\n# Dạng chỉ gán Reviewer + Limit\nPCD_Slot_Box_002\t-\treviewer_an\t100", language="text")
            
        elif mode == MODE_INSPECTION_AI:
            st.markdown("**Chức năng:** Tự động gán tài khoản vào mục Inspector.")
            st.markdown("**Cấu trúc:** 2 cột (Tên task + ID Inspector)")
            st.code("2D_TLD_Retouch_01\tinspect_thai_data\n2D_TLD_Retouch_02\tinspect_thai_data", language="text")
            
        elif mode == MODE_IMPORT_2D:
            st.markdown("**Chức năng:** Tự động tìm file trên cây thư mục zTree để upload cho Dự án 2D và bấm Reopen.")
            st.markdown("**Cấu trúc:** 2 cột (Tên task + Tên file đuôi .json/.zip hiển thị trên zTree)")
            st.code("2D_TLD_Retouch_001\t20260714_front_center_001.json", language="text")
            
        elif mode == MODE_IMPORT_3D:
            st.markdown("**Chức năng:** Tự động tìm file trên cây thư mục zTree để upload cho Dự án 3D và bấm Reopen.")
            st.markdown("**Cấu trúc:** 2 cột (Tên task + Tên file hiển thị trên zTree)")
            st.code("PCD_Parking_Slot_001\t20260714_parking_3d_001.json", language="text")
            
        elif mode == MODE_STATUS_SET:
            st.markdown("**Chức năng:** Mở Task Status Set, chọn mục 'Open' và chuyển trạng thái Step.")
            st.markdown("**Cấu trúc:** 2 cột (Tên task + Mã định danh giá trị Select box)")
            st.code("2D_TLD_Retouch_001\tSTEP02\n2D_TLD_Retouch_002\tSTEP03", language="text")

# --- HÀM BỔ TRỢ SELENIUM CORE ---
def wait_loading(driver):
    try:
        loading = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".loading-wrap")))
        WebDriverWait(driver, 60).until(lambda d: "on" not in (loading.get_attribute("class") or ""))
    except Exception: pass

def accept_alert_if_present(driver, timeout=2):
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        alert = driver.switch_to.alert; text = alert.text; alert.accept(); time.sleep(0.4)
        return text
    except Exception: return None

def check_and_switch_iframe(driver):
    try:
        driver.switch_to.default_content()
        if len(driver.find_elements(By.TAG_NAME, "iframe")) > 0:
            iframes = driver.find_elements(By.XPATH, "//iframe[contains(@id,'sub') or contains(@src,'task') or contains(@name,'Frame')]")
            if iframes: driver.switch_to.frame(iframes[0])
            else: driver.switch_to.frame(0)
    except Exception: pass

def open_search_form_if_needed(driver):
    accept_alert_if_present(driver, timeout=0.2)
    check_and_switch_iframe(driver)
    search_frm = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchFrm")))
    if "open" not in (search_frm.get_attribute("class") or ""):
        toggle_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick*='searchFrm']")))
        driver.execute_script("arguments[0].click();", toggle_btn)
        WebDriverWait(driver, 3).until(lambda d: "open" in (search_frm.get_attribute("class") or ""))

def input_task_name(driver, task_name):
    check_and_switch_iframe(driver)
    search_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchVal")))
    driver.execute_script("arguments[0].click();", search_input)
    search_input.send_keys(Keys.CONTROL, "a"); search_input.send_keys(Keys.DELETE); search_input.clear()
    search_input.send_keys(task_name); time.sleep(0.2)

def parse_uploaded_file(file_content):
    tasks = []
    lines = file_content.decode("utf-8-sig").splitlines()
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
        tasks.append({"line_no": line_no, "task_name": task_name, "col2": col2, "anno_point": anno_point, "rv_point": rv_point, "worker_id": worker_id, "reviewer_id": reviewer_id, "anno_limit": anno_limit})
    return tasks

# --- CORE LOGIC TÁC VỤ 7 CHẾ ĐỘ ---
def execute_mode_logic(driver, item, run_mode):
    driver.get(project_url); wait_loading(driver); accept_alert_if_present(driver, timeout=1); check_and_switch_iframe(driver)

    if run_mode in (MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET):
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); time.sleep(2); check_and_switch_iframe(driver)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#task_list > tr:nth-child(1)")))
        if "no data" in driver.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1)").text.lower():
            raise Exception(f"Không tìm thấy Task: {item['task_name']}")

        toggle_btn = driver.find_elements(By.XPATH, "//*[@id='task_list']/tr[1]//button[contains(@onclick, 'toggle')]")
        if toggle_btn: driver.execute_script("arguments[0].click();", toggle_btn[0])
        else: driver.execute_script("utils.fn.layer.toggle(event);")
        time.sleep(0.6)

    if run_mode in (MODE_IMPORT_2D, MODE_IMPORT_3D):
        check_and_switch_iframe(driver)
        import_link = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[@id='task_list']/tr[1]//ul//li/a[contains(normalize-space(), 'Import')]")))
        driver.execute_script("arguments[0].click();", import_link)
        WebDriverWait(driver, 60).until(lambda d: "importTask" in d.current_url); wait_loading(driver)
        
        check_and_switch_iframe(driver)
        driver.find_element(By.CSS_SELECTOR, "label[for=\"txtImportFileName\"]").click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#zTree")))
        tree_items = driver.find_elements(By.CSS_SELECTOR, "#zTree a")
        target = next((a for a in tree_items if (a.text or "").strip() == item["col2"].strip()), None)
        if not target: target = next((a for a in tree_items if item["col2"].strip() in (a.text or "").strip()), None)
        if not target: raise Exception(f"Không thấy file {item['col2']} trên zTree")
        driver.execute_script("arguments[0].click();", target)
        driver.find_element(By.CSS_SELECTOR, "#btn_upload").click()
        while True:
            try: WebDriverWait(driver, 2).until(EC.alert_is_present()); driver.switch_to.alert.accept()
            except Exception: break
        wait_loading(driver)
        
        driver.get(project_url); wait_loading(driver); open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); check_and_switch_iframe(driver)
        driver.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1) span.ellipsis.underline").click(); wait_loading(driver); check_and_switch_iframe(driver)
        reopen_btns = driver.find_elements(By.CSS_SELECTOR, "#taskReOpen")
        if reopen_btns:
            driver.execute_script("arguments[0].click();", reopen_btns[0])
            while True:
                try: WebDriverWait(driver, 2).until(EC.alert_is_present()); driver.switch_to.alert.accept()
                except Exception: break
            wait_loading(driver)

    elif run_mode == MODE_STATUS_SET:
        check_and_switch_iframe(driver)
        status_link = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[@id='task_list']/tr[1]//ul//li/a[contains(normalize-space(), 'Status') or contains(normalize-space(), '상태')]")))
        driver.execute_script("arguments[0].click();", status_link); wait_loading(driver); check_and_switch_iframe(driver)
        driver.find_element(By.CSS_SELECTOR, "label[for='radioOpen']").click()
        from selenium.webdriver.support.ui import Select
        el = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#openSelect")))
        if el.get_attribute("disabled") is None:
            Select(el).select_by_value(str(item["col2"]))
            driver.find_element(By.CSS_SELECTOR, "button[onclick='fnTaskStatusSet()']").click()
            while True:
                try: WebDriverWait(driver, 2).until(EC.alert_is_present()); driver.switch_to.alert.accept()
                except Exception: break
            wait_loading(driver)
            
    elif run_mode == MODE_ASSIGN_MASTER:
        completed_tab = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Completed Tasks']")))
        driver.execute_script("arguments[0].click();", completed_tab); wait_loading(driver)
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); check_and_switch_iframe(driver)
        rows = driver.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if not row: raise Exception("Không tìm thấy task")
        tds = row.find_elements(By.TAG_NAME, "td")
        driver.execute_script("arguments[0].click();", tds[1]); wait_loading(driver); check_and_switch_iframe(driver)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member']"))).click()
        driver.find_element(By.CSS_SELECTOR, "button.btn-member.add[onclick='searchMemberList(3)']").click()
        
        search_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
        search_input.send_keys(item["col2"])
        driver.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
        cb = driver.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
        driver.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
        driver.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=3)
        driver.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=5)

    elif run_mode == MODE_CHANGE_POINT:
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); check_and_switch_iframe(driver)
        rows = driver.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if not row: raise Exception("Không tìm thấy hàng dữ liệu")
        tds = row.find_elements(By.TAG_NAME, "td")
        driver.execute_script("arguments[0].click();", tds[1]); wait_loading(driver)
        driver.find_element(By.CSS_SELECTOR, "button.btn-s-point").click(); time.sleep(0.5)
        for key, val in [("#updateWorkPoint", item["anno_point"]), ("#updateReviewPoint", item["rv_point"])]:
            inp = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, key)))
            inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(val))
        driver.find_element(By.CSS_SELECTOR, "button.btn-l-point").click(); wait_loading(driver)

    elif run_mode == MODE_3D_ANNO_REVIEW:
        progress_tab = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//li[@onclick='ingtask()']")))
        driver.execute_script("arguments[0].click();", progress_tab); wait_loading(driver)
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); check_and_switch_iframe(driver)
        task_span = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#task_list > tr:nth-child(1) span.ellipsis.underline")))
        driver.execute_script("arguments[0].click();", task_span); wait_loading(driver)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member']"))).click()
        if item["worker_id"] and item["worker_id"].strip() not in ("-", "none", "None"):
            driver.find_element(By.CSS_SELECTOR, "button#button_WorkMember.btn-member.add[onclick*='searchMemberList(0)']").click()
            search_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
            search_input.send_keys(item["worker_id"])
            driver.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
            cb = driver.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
            driver.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
            driver.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        if item["anno_limit"]:
            inp = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#workAssignCnt")))
            inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(item["anno_limit"]))
        if item["reviewer_id"]:
            driver.find_element(By.CSS_SELECTOR, "button.btn-member.add[onclick*='searchMemberList(1)']").click()
            search_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
            search_input.send_keys(item["reviewer_id"])
            driver.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
            cb = driver.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
            driver.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
            driver.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
            accept_alert_if_present(driver, timeout=3)
        driver.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=5)

    elif run_mode == MODE_INSPECTION_AI:
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); check_and_switch_iframe(driver)
        rows = driver.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if row is None:
            completed_tab = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//li[contains(., 'Completed Tasks')]")))
            driver.execute_script("arguments[0].click();", completed_tab); wait_loading(driver)
            open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
            driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); check_and_switch_iframe(driver)
            rows = driver.find_elements(By.CSS_SELECTOR, "#task_list > tr")
            row = next((r for r in rows if item["task_name"] in r.text), None)
        if row is None: raise Exception("Không tìm thấy task")
        tds = row.find_elements(By.TAG_NAME, "td")
        driver.execute_script("arguments[0].click();", tds[1]); wait_loading(driver); check_and_switch_iframe(driver)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member']"))).click()
        role_title = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Inspector']")))
        current = role_title
        for _ in range(8):
            current = current.find_element(By.XPATH, "./..")
            if "Inspector" in current.text and "Persons" in current.text: panel = current; break
        driver.execute_script("arguments[0].click();", panel.find_element(By.CSS_SELECTOR, "button.btn-member.add"))
        search_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
        search_input.send_keys(item["col2"])
        driver.find_element(By.XPATH, "//button[contains(., 'Search')]").click(); time.sleep(1)
        cb = driver.find_element(By.CSS_SELECTOR, "input.memberChk")
        driver.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
        driver.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=3)
        driver.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=5)

# --- PHÂN ĐOẠN ĐỌC COOKIES VÀ KÍCH HOẠT CHẠY SCRIPT ---
if st.button("🚀 KÍCH HOẠT CHẠY AUTO", type="primary"):
    if not uploaded_file or not cookie_raw:
        st.error("Vui lòng tải lên file dữ liệu (.txt) và dán chuỗi Cookies JSON trước khi chạy!")
    else:
        # Cấu hình Chrome Headless tiết kiệm RAM tối đa cho Render
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=options)
        
        try:
            # 1. Gọi domain gốc để Selenium gán định danh vùng Cookie
            driver.get("https://www.ai-studio.co.kr/")
            time.sleep(1)
            driver.delete_all_cookies()
            
            # 2. Giải mã và nạp danh sách Cookie động
            cookies_list = json.loads(cookie_raw)
            for cookie in cookies_list:
                if 'sameSite' in cookie: del cookie['sameSite']
                driver.add_cookie(cookie)
                
            # 3. Phân tách file và chạy tự động gán task ngầm
            tasks = parse_uploaded_file(uploaded_file.read())
            
            progress_bar = st.progress(0)
            log_container = st.empty()
            logs = []
            
            for idx, item in enumerate(tasks, start=1):
                try:
                    execute_mode_logic(driver, item, mode)
                    msg = f"🟢 Dòng {item['line_no']} | Thành công | Task: {item['task_name']}"
                except Exception as e:
                    tb = e.__traceback__
                    while tb.tb_next: tb = tb.tb_next
                    line_err = tb.tb_lineno
                    err_type = type(e).__name__
                    error_clean = getattr(e, 'msg', str(e)).replace('\n', ' ').strip()
                    msg = f"🔴 Dòng {item['line_no']} | Thất bại dòng {line_err} ({err_type}): {error_clean[:100]} | Task: {item['task_name']}"
                    
                logs.append(msg)
                log_container.code("\n".join(logs))
                progress_bar.progress(idx / len(tasks))
                
            st.success("🎉 Bộ công cụ đã hoàn thành toàn bộ danh sách nhiệm vụ một cách an toàn!")
            
        except Exception as e:
            st.error(f"Lỗi hệ thống hoặc định dạng cấu trúc Cookies JSON không hợp lệ: {e}")
        finally:
            driver.quit()