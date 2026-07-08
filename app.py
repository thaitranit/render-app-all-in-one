#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import uuid
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
st.title("🤖 AI Studio Automation Suite")

# --- KHỞI TẠO BIẾN TRẠNG THÁI PHIÊN ---
if "step" not in st.session_state:
    st.session_state.step = "setup_account"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

# Khởi tạo Driver duy nhất (Singleton) xuyên suốt phiên làm việc
if "driver" not in st.session_state or st.session_state.driver is None:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,960")
    options.add_argument(f"--user-data-dir=/tmp/chrome_suite_{st.session_state.session_id}")
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(120)
    driver.get("https://www.ai-studio.co.kr/login")
    st.session_state.driver = driver

driver = st.session_state.driver

# --- CẤU TRÚC GIAO DIỆN HAI CỘT ---
col_left, col_right = st.columns([2, 1])

with col_left:
    project_url = st.text_input("1. Nhập URL Dự án (Project URL):", "https://www.ai-studio.co.kr/po/task/taskList?projectId=")
    uploaded_file = st.file_uploader("2. Tải lên File chứa danh sách Task (.txt):", type=["txt"])
    mode = st.selectbox("3. Lựa chọn chức năng Script muốn chạy:", [
        MODE_ASSIGN_MASTER, MODE_CHANGE_POINT, MODE_3D_ANNO_REVIEW, 
        MODE_INSPECTION_AI, MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET
    ])

with col_right:
    st.info(f"🆔 Session ID: `{st.session_state.session_id}`")
    st.markdown("### 📋 Hướng dẫn cấu trúc file mẫu (.txt)")
    with st.expander("📄 Xem cấu trúc chuẩn", expanded=True):
        if mode == MODE_ASSIGN_MASTER:
            st.code("2D_TLD_Pack006_001\tmaster_thai_01", language="text")
        elif mode == MODE_CHANGE_POINT:
            st.code("PCD_Parking_Slot_01\t15\t5", language="text")
        elif mode == MODE_3D_ANNO_REVIEW:
            st.code("PCD_Slot_Box_001\tworker_thai\treviewer_an\t50", language="text")
        elif mode == MODE_INSPECTION_AI:
            st.code("2D_TLD_Retouch_01\tinspect_thai_data", language="text")
        elif mode == MODE_IMPORT_2D or mode == MODE_IMPORT_3D:
            st.code("2D_TLD_Retouch_001\t20260714_front_center_001.json", language="text")
        elif mode == MODE_STATUS_SET:
            st.code("2D_TLD_Retouch_001\tSTEP02", language="text")

# --- CÁC HÀM BỔ TRỢ CORE LOGIC (GIỮ NGUYÊN) ---
def wait_loading(d):
    try: d.switch_to.default_content()
    except Exception: pass
    try:
        loading = WebDriverWait(d, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".loading-wrap")))
        WebDriverWait(d, 60).until(lambda x: "on" not in (loading.get_attribute("class") or ""))
    except Exception: pass

def accept_alert_if_present(d, timeout=2):
    try:
        d.switch_to.default_content()
        WebDriverWait(d, timeout).until(EC.alert_is_present())
        alert = d.switch_to.alert; txt = alert.text; alert.accept(); time.sleep(0.4)
        return txt
    except Exception: return None

def check_and_switch_iframe(d):
    try:
        d.switch_to.default_content()
        if len(d.find_elements(By.TAG_NAME, "iframe")) > 0:
            iframes = d.find_elements(By.XPATH, "//iframe[contains(@id,'sub') or contains(@src,'task') or contains(@name,'Frame')]")
            if iframes: d.switch_to.frame(iframes[0])
            else: d.switch_to.frame(0)
    except Exception: pass

def open_search_form_if_needed(d):
    accept_alert_if_present(d, timeout=0.2)
    check_and_switch_iframe(d)
    search_frm = WebDriverWait(d, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchFrm")))
    if "open" not in (search_frm.get_attribute("class") or ""):
        toggle_btn = WebDriverWait(d, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick*='searchFrm']")))
        d.execute_script("arguments[0].click();", toggle_btn)
        WebDriverWait(d, 3).until(lambda x: "open" in (search_frm.get_attribute("class") or ""))

def input_task_name(d, task_name):
    check_and_switch_iframe(d)
    search_input = WebDriverWait(d, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchVal")))
    d.execute_script("arguments[0].click();", search_input)
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

        tasks.append({
            "line_no": line_no, "task_name": task_name, "col2": col2,
            "anno_point": anno_point, "rv_point": rv_point,
            "worker_id": worker_id, "reviewer_id": reviewer_id, "anno_limit": anno_limit
        })
    return tasks

def execute_mode_logic(d, item, run_mode):
    d.get(project_url); wait_loading(d); accept_alert_if_present(d, timeout=1); check_and_switch_iframe(d)

    if run_mode in (MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET):
        open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        d.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(d); time.sleep(2); check_and_switch_iframe(d)
        WebDriverWait(d, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#task_list > tr:nth-child(1)")))
        if "no data" in d.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1)").text.lower():
            raise Exception(f"Không tìm thấy Task: {item['task_name']}")

        toggle_btn = d.find_elements(By.XPATH, "//*[@id='task_list']/tr[1]//button[contains(@onclick, 'toggle')]")
        if toggle_btn: d.execute_script("arguments[0].click();", toggle_btn[0])
        else: d.execute_script("utils.fn.layer.toggle(event);")
        time.sleep(0.6)

    if run_mode in (MODE_IMPORT_2D, MODE_IMPORT_3D):
        check_and_switch_iframe(d)
        import_link = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.XPATH, "//*[@id='task_list']/tr[1]//ul//li/a[contains(normalize-space(), 'Import')]")))
        d.execute_script("arguments[0].click();", import_link)
        WebDriverWait(d, 60).until(lambda x: "importTask" in x.current_url); wait_loading(d)
        
        check_and_switch_iframe(d)
        d.find_element(By.CSS_SELECTOR, "label[for=\"txtImportFileName\"]").click()
        WebDriverWait(d, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#zTree")))
        tree_items = d.find_elements(By.CSS_SELECTOR, "#zTree a")
        target = next((a for a in tree_items if (a.text or "").strip() == item["col2"].strip()), None)
        if not target: target = next((a for a in tree_items if item["col2"].strip() in (a.text or "").strip()), None)
        if not target: raise Exception(f"Không thấy file {item['col2']} trên zTree")
        d.execute_script("arguments[0].click();", target)
        d.find_element(By.CSS_SELECTOR, "#btn_upload").click()
        while True:
            try: WebDriverWait(d, 2).until(EC.alert_is_present()); d.switch_to.alert.accept()
            except Exception: break
        wait_loading(d)
        
        d.get(project_url); wait_loading(d); open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        d.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(d); check_and_switch_iframe(d)
        d.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1) span.ellipsis.underline").click(); wait_loading(d); check_and_switch_iframe(d)
        reopen_btns = d.find_elements(By.CSS_SELECTOR, "#taskReOpen")
        if reopen_btns:
            d.execute_script("arguments[0].click();", reopen_btns[0])
            while True:
                try: WebDriverWait(d, 2).until(EC.alert_is_present()); d.switch_to.alert.accept()
                except Exception: break
            wait_loading(d)

    elif run_mode == MODE_STATUS_SET:
        check_and_switch_iframe(d)
        status_link = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.XPATH, "//*[@id='task_list']/tr[1]//ul//li/a[contains(normalize-space(), 'Status') or contains(normalize-space(), '상태')]")))
        d.execute_script("arguments[0].click();", status_link); wait_loading(d); check_and_switch_iframe(d)
        d.find_element(By.CSS_SELECTOR, "label[for='radioOpen']").click()
        from selenium.webdriver.support.ui import Select
        el = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#openSelect")))
        if el.get_attribute("disabled") is None:
            Select(el).select_by_value(str(item["col2"]))
            d.find_element(By.CSS_SELECTOR, "button[onclick='fnTaskStatusSet()']").click()
            while True:
                try: WebDriverWait(d, 2).until(EC.alert_is_present()); d.switch_to.alert.accept()
                except Exception: break
            wait_loading(d)
            
    elif run_mode == MODE_ASSIGN_MASTER:
        completed_tab = WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Completed Tasks']")))
        d.execute_script("arguments[0].click();", completed_tab); wait_loading(d)
        open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        d.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(d); check_and_switch_iframe(d)
        rows = d.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if not row: raise Exception("Không tìm thấy task")
        tds = row.find_elements(By.TAG_NAME, "td")
        d.execute_script("arguments[0].click();", tds[1]); wait_loading(d); check_and_switch_iframe(d)
        WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member']"))).click()
        d.find_element(By.CSS_SELECTOR, "button.btn-member.add[onclick='searchMemberList(3)']").click()
        
        search_input = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
        search_input.send_keys(item["col2"])
        d.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
        cb = d.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
        d.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
        d.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        accept_alert_if_present(d, timeout=3)
        d.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(d, timeout=5)

    elif run_mode == MODE_CHANGE_POINT:
        open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        d.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(d); check_and_switch_iframe(d)
        rows = d.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if not row: raise Exception("Không tìm thấy hàng dữ liệu")
        tds = row.find_elements(By.TAG_NAME, "td")
        d.execute_script("arguments[0].click();", tds[1]); wait_loading(d)
        d.find_element(By.CSS_SELECTOR, "button.btn-s-point").click(); time.sleep(0.5)
        for key, val in [("#updateWorkPoint", item["anno_point"]), ("#updateReviewPoint", item["rv_point"])]:
            inp = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, key)))
            inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(val))
        d.find_element(By.CSS_SELECTOR, "button.btn-l-point").click(); wait_loading(d)

    elif run_mode == MODE_3D_ANNO_REVIEW:
        progress_tab = WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, "//li[@onclick='ingtask()']")))
        d.execute_script("arguments[0].click();", progress_tab); wait_loading(d)
        open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        d.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(d); check_and_switch_iframe(d)
        task_span = WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#task_list > tr:nth-child(1) span.ellipsis.underline")))
        d.execute_script("arguments[0].click();", task_span); wait_loading(d)
        WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member']"))).click()
        if item["worker_id"] and item["worker_id"].strip() not in ("-", "none", "None"):
            d.find_element(By.CSS_SELECTOR, "button#button_WorkMember.btn-member.add[onclick*='searchMemberList(0)']").click()
            search_input = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
            search_input.send_keys(item["worker_id"])
            d.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
            cb = d.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
            d.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
            d.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        if item["anno_limit"]:
            inp = WebDriverWait(d, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#workAssignCnt")))
            inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(item["anno_limit"]))
        if item["reviewer_id"]:
            d.find_element(By.CSS_SELECTOR, "button.btn-member.add[onclick*='searchMemberList(1)']").click()
            search_input = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
            search_input.send_keys(item["reviewer_id"])
            d.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
            cb = d.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
            d.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
            d.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
            accept_alert_if_present(d, timeout=3)
        d.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(d, timeout=5)

    elif run_mode == MODE_INSPECTION_AI:
        open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        d.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(d); check_and_switch_iframe(d)
        rows = d.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if row is None:
            completed_tab = WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, "//li[contains(., 'Completed Tasks')]")))
            d.execute_script("arguments[0].click();", completed_tab); wait_loading(d)
            open_search_form_if_needed(d); input_task_name(d, item["task_name"])
            d.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(d); check_and_switch_iframe(d)
            rows = d.find_elements(By.CSS_SELECTOR, "#task_list > tr")
            row = next((r for r in rows if item["task_name"] in r.text), None)
        if row is None: raise Exception("Không tìm thấy task")
        tds = row.find_elements(By.TAG_NAME, "td")
        d.execute_script("arguments[0].click();", tds[1]); wait_loading(d); check_and_switch_iframe(d)
        WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member']"))).click()
        role_title = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Inspector']")))
        current = role_title
        for _ in range(8):
            current = current.find_element(By.XPATH, "./..")
            if "Inspector" in current.text and "Persons" in current.text: panel = current; break
        d.execute_script("arguments[0].click();", panel.find_element(By.CSS_SELECTOR, "button.btn-member.add"))
        search_input = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
        search_input.send_keys(item["col2"])
        d.find_element(By.XPATH, "//button[contains(., 'Search')]").click(); time.sleep(1)
        cb = d.find_element(By.CSS_SELECTOR, "input.memberChk")
        d.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
        d.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        accept_alert_if_present(d, timeout=3)
        d.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(d, timeout=5)

# =========================================================
# LUỒNG ĐIỀU KHIỂN ĐĂNG NHẬP TINH GỌN (THEO Ý TƯỞNG MỚI)
# =========================================================

# CHẾ ĐỘ 1: BẬT MÀN HÌNH TƯƠNG TÁC ĐỂ USER TỰ ĐĂNG NHẬP VÀ ĐIỀN OTP TẠI CHỖ
if st.session_state.step == "setup_account":
    st.subheader("🖥️ Màn hình đăng nhập AI-Studio thực tế từ Server")
    st.info("💡 Bạn chỉ việc gõ thông tin, OTP rồi click trực tiếp trên ảnh giống như dùng máy tính bình thường.")
    
    # Render màn hình động theo thời gian thực
    screenshot_path = f"/tmp/render_screen_{st.session_state.session_id}.png"
    driver.save_screenshot(screenshot_path)
    
    # 1. Khung hiển thị tương tác trực quan duy nhất
    st.image(screenshot_path, caption="Cửa sổ AI-Studio Live View")
    
    # 2. Khung thao tác điều khiển nhanh
    c1, c2 = st.columns(2)
    with c1:
        text_payload = st.text_input("✍️ Nhập chuỗi (ID / Password / OTP):", key="p_txt")
        if st.button("⌨️ Gửi phím chữ (Dán vào ô đang nhấp nháy)"):
            if text_payload:
                try:
                    active_el = driver.switch_to.active_element
                    active_el.click()
                    active_el.send_keys(Keys.CONTROL, "a")
                    active_el.send_keys(Keys.DELETE)
                    active_el.send_keys(text_payload)
                    st.rerun()
                except Exception as e: st.error(str(e))
                
        st.markdown("**Nút bấm nhanh:**")
        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("Bấm nút Đăng nhập"):
                try: driver.find_element(By.XPATH, "//button[@type='submit']").click(); time.sleep(2.5); st.rerun()
                except Exception: pass
        with sc2:
            if st.button("Bấm Xác nhận OTP"):
                try: driver.find_element(By.XPATH, "//button[contains(., 'Confirm') or contains(., '인증')]").click(); time.sleep(3); st.rerun()
                except Exception: pass
                
    with c2:
        if st.button("🔄 CẬP NHẬT LẠI ẢNH MÀN HÌNH (REFRESH)"):
            st.rerun()
            
        st.write("---")
        # Nút thắt cốt lõi: Khi bấm nút này, CỬA SỔ ĐĂNG NHẬP ẨN ĐI hoàn toàn, app chuyển sang chế độ chạy Auto ngầm
        if st.button("🚀 ĐÃ ĐĂNG NHẬP THÀNH CÔNG -> ẨN CỬA SỔ & CHẠY AUTO", type="primary"):
            st.session_state.step = "auto_processing"
            st.rerun()

# CHẾ ĐỘ 2: ẨN HOÀN TOÀN MÀN HÌNH LOGIN, CHỈ HIỂN THỊ TIẾN TRÌNH CHẠY SCRIPT TỰ ĐỘNG
elif st.session_state.step == "auto_processing":
    st.subheader("⚙️ Toàn bộ hệ thống đang xử lý tự động ngầm...")
    
    if st.button("↩️ Bật lại cửa sổ Login (Nếu cần Đăng nhập lại)"):
        st.session_state.step = "setup_account"
        st.rerun()
        
    try:
        if not uploaded_file:
            st.error("Vui lòng tải lên file chứa danh sách task (.txt) ở cột bên trái!"); st.stop()
            
        tasks = parse_uploaded_file(uploaded_file.read())
        driver.get(project_url)
        wait_loading(driver)
        
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
                if not error_clean or error_clean == "Message:": error_clean = str(e).strip().replace('\n', ' ')
                if len(error_clean) > 130: error_clean = error_clean[:130] + "..."
                    
                msg = f"🔴 Dòng {item['line_no']} | Lỗi dòng code {line_err} ({err_type}): {error_clean} | Task: {item['task_name']}"
                
            logs.append(msg)
            log_container.code("\n".join(logs))
            progress_bar.progress(idx / len(tasks))
            
        st.success("🎉 Bộ công cụ đã hoàn thành toàn bộ danh sách nhiệm vụ một cách an toàn!")
        
    except Exception as e:
        st.error(f"Lỗi hệ thống phát sinh: {e}")