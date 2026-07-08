#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import uuid
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
st.title("🤖 AI Studio Automation Suite - Live Session Edition")

# --- BIẾN LƯU TRẠNG THÁI PHIÊN LÀM VIỆC CỐ ĐỊNH ---
if "step" not in st.session_state:
    st.session_state.step = "login_screen"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

# Khởi tạo driver cố định duy nhất cho phiên làm việc, không bao giờ tạo lại khi đổi bước
if "driver" not in st.session_state or st.session_state.driver is None:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-data-dir=/tmp/chrome_live_{st.session_state.session_id}")
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(120)
    # Vào sẵn trang chủ đăng nhập ban đầu
    driver.get("https://www.ai-studio.co.kr/login")
    st.session_state.driver = driver

driver = st.session_state.driver

# --- GIAO DIỆN PHÂN CHIA CỘT ---
col_left, col_right = st.columns([2, 1])

with col_left:
    project_url = st.text_input("1. Nhập URL Dự án (Project URL):", "https://www.ai-studio.co.kr/po/task/taskList?projectId=")
    uploaded_file = st.file_uploader("2. Tải lên File chứa danh sách Task (.txt):", type=["txt"])
    mode = st.selectbox("3. Lựa chọn chức năng Script muốn chạy:", [
        MODE_ASSIGN_MASTER, MODE_CHANGE_POINT, MODE_3D_ANNO_REVIEW, 
        MODE_INSPECTION_AI, MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET
    ])

with col_right:
    st.info(f"🆔 Phiên làm việc: `{st.session_state.session_id}`")
    st.markdown("### 📋 Hướng dẫn file cấu hình mẫu (.txt)")
    with st.expander("📄 Xem cấu trúc chuẩn theo chức năng đang chọn", expanded=True):
        if mode == MODE_ASSIGN_MASTER:
            st.code("2D_TLD_Pack006_001\tmaster_thai_01\n2D_TLD_Pack006_002\tmaster_thai_01", language="text")
        elif mode == MODE_CHANGE_POINT:
            st.code("PCD_Parking_Slot_01\t15\t5\nPCD_Parking_Slot_02\t20\t10", language="text")
        elif mode == MODE_3D_ANNO_REVIEW:
            st.code("PCD_Slot_Box_001\tworker_thai\treviewer_an\t50\nPCD_Slot_Box_002\t-\treviewer_an\t100", language="text")
        elif mode == MODE_INSPECTION_AI:
            st.code("2D_TLD_Retouch_01\tinspect_thai_data", language="text")
        elif mode == MODE_IMPORT_2D or mode == MODE_IMPORT_3D:
            st.code("2D_TLD_Retouch_001\t20260714_front_center_001.json", language="text")
        elif mode == MODE_STATUS_SET:
            st.code("2D_TLD_Retouch_001\tSTEP02", language="text")

# --- HÀM BỔ TRỢ SELENIUM CORE ---
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
        alert = d.switch_to.alert
        txt = alert.text
        alert.accept()
        time.sleep(0.4)
        return txt
    except Exception: return None

def robust_click(d, elem, name="element"):
    for fn in (lambda: elem.click(), lambda: d.execute_script("arguments[0].click();", elem)):
        try:
            d.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
            time.sleep(0.2)
            fn()
            return
        except Exception: time.sleep(0.2)
    raise Exception(f"Failed to click {name}")

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
        robust_click(d, toggle_btn, "search form toggle")
        WebDriverWait(d, 3).until(lambda x: "open" in (search_frm.get_attribute("class") or ""))

def input_task_name(d, task_name):
    check_and_switch_iframe(d)
    search_input = WebDriverWait(d, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchVal")))
    robust_click(d, search_input, "Task Search Input")
    search_input.send_keys(Keys.CONTROL, "a")
    search_input.send_keys(Keys.DELETE)
    search_input.clear()
    search_input.send_keys(task_name)
    time.sleep(0.2)

def execute_mode_logic(d, item, run_mode):
    d.get(project_url)
    wait_loading(d)
    accept_alert_if_present(d, timeout=1)
    check_and_switch_iframe(d)

    if run_mode in (MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET):
        open_search_form_if_needed(d)
        input_task_name(d, item["task_name"])
        robust_click(d, d.find_element(By.CSS_SELECTOR, "#btn_search"), "search")
        wait_loading(d)
        time.sleep(2)

        check_and_switch_iframe(d)
        WebDriverWait(d, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#task_list > tr:nth-child(1)")))
        if "no data" in d.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1)").text.lower():
            raise Exception(f"Không tìm thấy Task: {item['task_name']}")

        toggle_btn = None
        toggle_xpaths = [
            "//*[@id='task_list']/tr[1]//button[contains(@onclick, 'toggle')]",
            "//*[@id='task_list']/tr[1]//a[contains(@onclick, 'toggle')]",
            "//*[@id='task_list']/tr[1]/td[last()]//button",
            "//button[contains(@onclick, 'utils.fn.layer.toggle')]"
        ]
        for xp in toggle_xpaths:
            btns = d.find_elements(By.XPATH, xp)
            if btns: toggle_btn = btns[0]; break

        if toggle_btn:
            d.execute_script("arguments[0].click();", toggle_btn)
        else:
            d.execute_script("utils.fn.layer.toggle(event);")
        time.sleep(0.6)

    # Nhánh Import/Status Set (Giữ nguyên toàn bộ logic iframe kiên cố từ bản trước)
    if run_mode in (MODE_IMPORT_2D, MODE_IMPORT_3D):
        check_and_switch_iframe(d)
        import_link = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.XPATH, "//*[@id='task_list']/tr[1]//ul//li/a[contains(normalize-space(), 'Import')]")))
        d.execute_script("arguments[0].click();", import_link)
        WebDriverWait(d, 60).until(lambda x: "importTask" in x.current_url); wait_loading(d)
        
        check_and_switch_iframe(d)
        robust_click(d, d.find_element(By.CSS_SELECTOR, "label[for=\"txtImportFileName\"]"), "Open zTree")
        WebDriverWait(d, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#zTree")))
        tree_items = d.find_elements(By.CSS_SELECTOR, "#zTree a")
        target = next((a for a in tree_items if (a.text or "").strip() == item["col2"].strip()), None)
        if not target: target = next((a for a in tree_items if item["col2"].strip() in (a.text or "").strip()), None)
        if not target: raise Exception(f"Không thấy file {item['col2']} trên zTree")
        robust_click(d, target, "Select tree file")
        d.find_element(By.CSS_SELECTOR, "#btn_upload").click()
        while True:
            try: WebDriverWait(d, 2).until(EC.alert_is_present()); d.switch_to.alert.accept()
            except Exception: break
        wait_loading(d)
        
        d.get(project_url); wait_loading(d); open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        robust_click(d, d.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); wait_loading(d)
        check_and_switch_iframe(d)
        robust_click(d, d.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1) span.ellipsis.underline"), "Task Detail")
        wait_loading(d)
        check_and_switch_iframe(d)
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
        d.execute_script("arguments[0].click();", status_link)
        wait_loading(d)
        check_and_switch_iframe(d)
        robust_click(d, d.find_element(By.CSS_SELECTOR, "label[for='radioOpen']"), "Radio Open")
        from selenium.webdriver.support.ui import Select
        el = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#openSelect")))
        if el.get_attribute("disabled") is None:
            Select(el).select_by_value(str(item["col2"]))
            robust_click(d, d.find_element(By.CSS_SELECTOR, "button[onclick='fnTaskStatusSet()']"), "Save")
            while True:
                try: WebDriverWait(d, 2).until(EC.alert_is_present()); d.switch_to.alert.accept()
                except Exception: break
            wait_loading(d)
            
    elif run_mode == MODE_ASSIGN_MASTER:
        completed_tab = WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Completed Tasks']")))
        robust_click(d, completed_tab, "Completed Tasks tab"); wait_loading(d)
        open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        robust_click(d, d.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); wait_loading(d)
        check_and_switch_iframe(d)
        rows = d.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if not row: raise Exception("Không tìm thấy task trong Completed Tasks")
        tds = row.find_elements(By.TAG_NAME, "td")
        robust_click(d, tds[1], "click task detail")
        wait_loading(d)
        open_member_tab(d)
        robust_click(d, d.find_element(By.CSS_SELECTOR, "button.btn-member.add[onclick='searchMemberList(3)']"), "Add Master")
        
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
        robust_click(d, d.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); wait_loading(d)
        check_and_switch_iframe(d)
        rows = d.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if not row: raise Exception("Không tìm thấy hàng dữ liệu của Task")
        tds = row.find_elements(By.TAG_NAME, "td")
        robust_click(d, tds[1], "click cell")
        wait_loading(d)
        robust_click(d, d.find_element(By.CSS_SELECTOR, "button.btn-s-point"), "open point popup"); time.sleep(0.5)
        for key, val in [("#updateWorkPoint", item["anno_point"]), ("#updateReviewPoint", item["rv_point"])]:
            inp = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, key)))
            inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(val))
        robust_click(d, d.find_element(By.CSS_SELECTOR, "button.btn-l-point"), "Confirm Point"); wait_loading(d)

    elif run_mode == MODE_3D_ANNO_REVIEW:
        progress_tab = WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, "//li[@onclick='ingtask()']")))
        robust_click(d, progress_tab, "In-progress Tasks tab"); wait_loading(d)
        open_search_form_if_needed(d); input_task_name(d, item["task_name"])
        robust_click(d, d.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); wait_loading(d)
        check_and_switch_iframe(d)
        WebDriverWait(d, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#task_list > tr")))
        task_span = WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#task_list > tr:nth-child(1) span.ellipsis.underline")))
        robust_click(d, task_span, "First task row"); wait_loading(d)
        open_member_tab(d)
        if item["worker_id"] and item["worker_id"].strip() not in ("-", "none", "None"):
            robust_click(d, d.find_element(By.CSS_SELECTOR, "button#button_WorkMember.btn-member.add[onclick*='searchMemberList(0)']"), "Worker Popup")
            search_input = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.ID, "searchId")))
            search_input.send_keys(item["worker_id"])
            d.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
            cb = d.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
            d.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", cb)
            d.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        if item["anno_limit"]:
            inp = WebDriverWait(d, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#workAssignCnt")))
            d.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
            inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(item["anno_limit"]))
        if item["reviewer_id"]:
            robust_click(d, d.find_element(By.CSS_SELECTOR, "button.btn-member.add[onclick*='searchMemberList(1)']"), "Reviewer Popup")
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
        robust_click(d, d.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); wait_loading(d)
        check_and_switch_iframe(d)
        rows = d.find_elements(By.CSS_SELECTOR, "#task_list > tr")
        row = next((r for r in rows if item["task_name"] in r.text), None)
        if row is None:
            completed_tab = WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, "//li[contains(., 'Completed Tasks')]")))
            robust_click(d, completed_tab, "Completed Tasks"); wait_loading(d)
            open_search_form_if_needed(d); input_task_name(d, item["task_name"])
            robust_click(d, d.find_element(By.CSS_SELECTOR, "#btn_search"), "search"); wait_loading(d)
            check_and_switch_iframe(d)
            rows = d.find_elements(By.CSS_SELECTOR, "#task_list > tr")
            row = next((r for r in rows if item["task_name"] in r.text), None)
        if row is None: raise Exception("Không tìm thấy hàng dữ liệu của Task")
        tds = row.find_elements(By.TAG_NAME, "td")
        robust_click(d, tds[1], "click cell")
        wait_loading(d)
        open_member_tab(d)
        role_title = WebDriverWait(d, 10).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Inspector']")))
        current = role_title
        for _ in range(8):
            current = current.find_element(By.XPATH, "./..")
            if "Inspector" in current.text and "Persons" in current.text: panel = current; break
        robust_click(d, panel.find_element(By.CSS_SELECTOR, "button.btn-member.add"), "Add Inspector")
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
# LUỒNG ĐĂNG NHẬP LIVE TRỰC TIẾP TRÊN INTERFACE WEB
# =========================================================

# --- BƯỚC 1 & 2: MÀN HÌNH ĐĂNG NHẬP LIVE (TỰ DO DIỄN RA TRÊN SCREENSHOT) ---
if st.session_state.step == "login_screen":
    st.subheader("🖥️ Bảng điều khiển Đăng nhập Trình duyệt ngầm")
    st.warning("Bạn hãy sử dụng Form dưới đây để thực hiện mọi hành động đăng nhập trực tiếp (Điền ID/Mật khẩu/OTP bằng tay).")
    
    # Chụp ảnh và hiển thị màn hình thực tế liên tục
    screenshot_path = f"/tmp/live_screen_{st.session_state.session_id}.png"
    driver.save_screenshot(screenshot_path)
    st.image(screenshot_path, caption="Màn hình Tr trình duyệt ngầm thực tế (AI-Studio)")
    
    # Các ô điều hướng click chuột/bấm phím từ xa
    col1, col2, col3 = st.columns(3)
    with col1:
        remote_id = st.text_input("Gõ text từ xa (ID / Pass / OTP):", key="txt_remote")
        xpath_input = st.text_input("Nhập XPath của ô muốn điền (Hoặc để trống tự dò):", "")
        if st.button("⌨️ ĐIỀN CHỮ VÀO Ô NGẦM", type="secondary"):
            if remote_id:
                try:
                    if xpath_input: el = driver.find_element(By.XPATH, xpath_input)
                    else: el = driver.switch_to.active_element
                    el.click(); el.send_keys(Keys.CONTROL, "a"); el.send_keys(Keys.DELETE)
                    el.send_keys(remote_id); st.rerun()
                except Exception as e: st.error(f"Lỗi nhập chữ: {e}")
                
    with col2:
        click_xpath = st.text_input("Nhập XPath nút muốn bấm (Hoặc dùng nút mẫu dưới):", "")
        if st.button("🖱️ CLICK CHUỘT THEO XPATH"):
            if click_xpath:
                try: driver.find_element(By.XPATH, click_xpath).click(); time.sleep(2); st.rerun()
                except Exception as e: st.error(f"Lỗi click: {e}")
        
        # Các nút bấm mẫu định hình nhanh
        st.markdown("**Nút bấm nhanh hệ thống:**")
        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            if st.button("Bấm nút Login"):
                try: driver.find_element(By.XPATH, "//button[@type='submit']").click(); time.sleep(3); st.rerun()
                except Exception: pass
        with sub_col2:
            if st.button("Bấm nút Confirm OTP"):
                try: driver.find_element(By.XPATH, "//button[contains(., 'Confirm') or contains(., '인증') or contains(@onclick, 'login')]").click(); time.sleep(4); st.rerun()
                except Exception: pass

    with col3:
        st.success("🔄 Trạng thái điều hướng:")
        if st.button("📸 CẬP NHẬT LẠI ẢNH MÀN HÌNH (REFRESH)"):
            st.rerun()
            
        if st.button("🔓 ĐÃ LOGIN THÀNH CÔNG -> VÀO PHẦN CHẠY AUTO", type="primary"):
            st.session_state.step = "running"
            st.rerun()

# --- BƯỚC 3: TIẾN TRÌNH THỰC THI CHẠY KHỐI CÀY TASK TỰ ĐỘNG ---
elif st.session_state.step == "running":
    st.subheader("🚀 Đang tiến hành gán Task tự động ngầm theo Session...")
    
    if st.button("↩️ Quay lại màn hình Login (Nếu bị văng tài khoản)"):
        st.session_state.step = "login_screen"; st.rerun()
        
    try:
        if not uploaded_file:
            st.error("Vui lòng quay lại upload file danh sách task!"); st.stop()
            
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
                    
                msg = f"🔴 Dòng {item['line_no']} | Thất bại dòng {line_err} ({err_type}): {error_clean} | Task: {item['task_name']}"
                
                # Chụp bằng chứng lỗi xuất ra giao diện web
                try:
                    debug_screenshot = f"/tmp/error_line_{line_err}.png"
                    driver.save_screenshot(debug_screenshot)
                    st.error(f"📸 Ảnh bằng chứng lỗi hàng {item['line_no']}:")
                    st.image(debug_screenshot)
                except Exception: pass
                
            logs.append(msg)
            log_container.code("\n".join(logs))
            progress_bar.progress(idx / len(tasks))
            
        st.success("🎉 Bộ công cụ đã hoàn thành toàn bộ file danh sách nhiệm vụ!")
        
    except Exception as e:
        st.error(f"Lỗi hệ thống: {e}")