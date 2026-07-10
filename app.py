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
from selenium.common.exceptions import TimeoutException

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
    
    # 🔑 Ô dán Cookies thông minh
    cookie_raw = st.text_area("4. Dán chuỗi Cookies của bạn vào đây (Đã sao chép từ Cookie-Editor dưới dạng JSON):", height=150, 
                              placeholder='[{"name": "JSESSIONID", "value": "..."}, ...]')

# --- KHÔI PHỤC HOÀN TOÀN KHỐI HƯỚNG DẪN VÀ FILE CẤU TRÚC MẪU PHÍA PHẢI ---
with col_right:
    st.info("💡 **Hướng dẫn lấy Cookie nhanh cho Worker:**\n1. Đăng nhập vào `ai-studio.co.kr` trên trình duyệt Chrome máy cá nhân.\n2. Cài extension **Cookie-Editor**.\n3. Bấm vào icon extension $\rightarrow$ Chọn **Export** $\rightarrow$ Chọn định dạng **JSON**.\n4. Dán toàn bộ chuỗi text vừa copy vào ô bên cạnh rồi bấm chạy.")
    
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
def wait_loading(driver):
    try:
        loading = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".loading-wrap")))
        WebDriverWait(driver, 90).until(lambda d: "on" not in (loading.get_attribute("class") or "")) # Tăng thời gian chờ Loading-wrap lên hẳn 90s
    except Exception: pass

def accept_alert_if_present(driver, timeout=3):
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        alert = driver.switch_to.alert; text = alert.text; alert.accept(); time.sleep(0.5)
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

def robust_click(driver, elem, name="element"):
    for fn in (lambda: elem.click(), lambda: driver.execute_script("arguments[0].click();", elem)):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
            time.sleep(0.3)
            fn()
            return
        except Exception: time.sleep(0.3)
    raise Exception(f"Failed to click {name}")

def open_search_form_if_needed(driver):
    accept_alert_if_present(driver, timeout=0.5)
    check_and_switch_iframe(driver)
    search_frm = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchFrm")))
    if "open" not in (search_frm.get_attribute("class") or ""):
        toggle_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick*='searchFrm']")))
        driver.execute_script("arguments[0].click();", toggle_btn)
        WebDriverWait(driver, 5).until(lambda d: "open" in (search_frm.get_attribute("class") or ""))

def input_task_name(driver, task_name):
    check_and_switch_iframe(driver)
    search_input = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchVal")))
    driver.execute_script("arguments[0].click();", search_input)
    search_input.send_keys(Keys.CONTROL, "a"); search_input.send_keys(Keys.DELETE); search_input.clear()
    search_input.send_keys(task_name); time.sleep(0.3)

def find_matching_row(driver, task_name):
    check_and_switch_iframe(driver)
    rows = driver.find_elements(By.CSS_SELECTOR, "#task_list > tr")
    for row in rows:
        try:
            txt = " | ".join(td.text.strip() for td in row.find_elements(By.TAG_NAME, "td"))
            if task_name in txt: return row
        except Exception: continue
    return None

def click_task_name_from_row(driver, row, task_name):
    tds = row.find_elements(By.TAG_NAME, "td")
    task_name_cell = tds[1]
    anchors = task_name_cell.find_elements(By.TAG_NAME, "a")
    if anchors:
        robust_click(driver, anchors[0], "task name anchor")
        return
    descendants = task_name_cell.find_elements(By.XPATH, ".//*")
    for elem in descendants:
        try:
            if task_name in (elem.text or ""):
                robust_click(driver, elem, "task name descendant")
                return
        except Exception: continue
    robust_click(driver, task_name_cell, "task name cell")

def parse_uploaded_file(file_content):
    tasks = []
    lines = file_content.decode("utf-8-sig").splitlines()
    for line_no, line in enumerate(lines, start=1):
        raw = line.strip()
        if not raw or raw.startswith("#"): continue
        parts = raw.split("\t") if "\t" in raw else (raw.split(",") if "," in raw else raw.split())
        if len(parts) < 2: continue
        task_name, col2 = parts[0].strip(), parts[1].strip()
        anno_point, rv_point = "0", "0"
        worker_id, reviewer_id, anno_limit = None, None, None
        if len(parts) == 2: worker_id = parts[1].strip()
        else:
            if parts[1].strip().isdigit() and parts[2].strip().isdigit(): 
                anno_point, rv_point = parts[1].strip(), parts[2].strip()
            else:
                worker_id = parts[1].strip()
                if len(parts) >= 3:
                    if parts[2].strip().isdigit(): anno_limit = parts[2].strip()
                    else: reviewer_id = parts[2].strip()
                if len(parts) >= 4 and parts[3].strip().isdigit(): anno_limit = parts[3].strip()
        tasks.append({"line_no": line_no, "task_name": task_name, "col2": col2, "anno_point": anno_point, "rv_point": rv_point, "worker_id": worker_id, "reviewer_id": reviewer_id, "anno_limit": anno_limit})
    return tasks

# --- CORE LOGIC TÁC VỤ 7 CHẾ ĐỘ ---
def execute_mode_logic(driver, item, run_mode):
    driver.get(project_url); wait_loading(driver); accept_alert_if_present(driver, timeout=1); check_and_switch_iframe(driver)

    if run_mode in (MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET):
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver)
        time.sleep(4) 
        check_and_switch_iframe(driver)
        
        WebDriverWait(driver, 45).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#task_list > tr:nth-child(1)")))
        if "no data" in driver.find_element(By.CSS_SELECTOR, "#task_list > tr:nth-child(1)").text.lower():
            raise Exception(f"Không tìm thấy Task: {item['task_name']}")

        toggle_btn = driver.find_elements(By.XPATH, "//*[@id='task_list']/tr[1]//button[contains(@onclick, 'toggle')]")
        if toggle_btn: driver.execute_script("arguments[0].click();", toggle_btn[0])
        else: driver.execute_script("utils.fn.layer.toggle(event);")
        time.sleep(1)

    if run_mode in (MODE_IMPORT_2D, MODE_IMPORT_3D):
        check_and_switch_iframe(driver)
        import_link = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//*[@id='task_list']/tr[1]//ul//li/a[contains(normalize-space(), 'Import')]")))
        driver.execute_script("arguments[0].click();", import_link)
        WebDriverWait(driver, 60).until(lambda d: "importTask" in d.current_url); wait_loading(driver)
        
        check_and_switch_iframe(driver)
        driver.find_element(By.CSS_SELECTOR, "label[for=\"txtImportFileName\"]").click()
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#zTree")))
        tree_items = driver.find_elements(By.CSS_SELECTOR, "#zTree a")
        target = next((a for a in tree_items if (a.text or "").strip() == item["col2"].strip()), None)
        if not target: target = next((a for a in tree_items if item["col2"].strip() in (a.text or "").strip()), None)
        if not target: raise Exception(f"Không thấy file {item['col2']} trên zTree")
        driver.execute_script("arguments[0].click();", target)
        driver.find_element(By.CSS_SELECTOR, "#btn_upload").click()
        while True:
            try: WebDriverWait(driver, 3).until(EC.alert_is_present()); driver.switch_to.alert.accept()
            except Exception: break
        wait_loading(driver)
        
        driver.get(project_url); wait_loading(driver); open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); time.sleep(3); check_and_switch_iframe(driver)
        
        row = find_matching_row(driver, item["task_name"])
        if not row: raise Exception("Không tìm thấy hàng dữ liệu sau khi Import")
        click_task_name_from_row(driver, row, item["task_name"])
        wait_loading(driver); check_and_switch_iframe(driver)
        
        reopen_btns = driver.find_elements(By.CSS_SELECTOR, "#taskReOpen")
        if reopen_btns:
            driver.execute_script("arguments[0].click();", reopen_btns[0])
            while True:
                try: WebDriverWait(driver, 3).until(EC.alert_is_present()); driver.switch_to.alert.accept()
                except Exception: break
            wait_loading(driver)

    elif run_mode == MODE_STATUS_SET:
        check_and_switch_iframe(driver)
        status_link = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//*[@id='task_list']/tr[1]//ul//li/a[contains(normalize-space(), 'Status') or contains(normalize-space(), '상태')]")))
        driver.execute_script("arguments[0].click();", status_link); wait_loading(driver); check_and_switch_iframe(driver)
        driver.find_element(By.CSS_SELECTOR, "label[for='radioOpen']").click()
        from selenium.webdriver.support.ui import Select
        el = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#openSelect")))
        if el.get_attribute("disabled") is None:
            Select(el).select_by_value(str(item["col2"]))
            driver.find_element(By.CSS_SELECTOR, "button[onclick='fnTaskStatusSet()']").click()
            while True:
                try: WebDriverWait(driver, 3).until(EC.alert_is_present()); driver.switch_to.alert.accept()
                except Exception: break
            wait_loading(driver)
            
    elif run_mode == MODE_ASSIGN_MASTER:
        # 🛠️ KIỂM TRA ĐIỀU KIỆN ĐẶC BIỆT: Nếu hệ thống đã tự nhảy vào trang "Task Details" luôn (như trên Railway)
        if "taskDetails" in driver.current_url or len(driver.find_elements(By.XPATH, "//*[normalize-space()='Task Details']")) > 0:
            pass # Đã đứng sẵn trong trang chi tiết, không cần thực hiện quét tìm bảng tổng nữa
        else:
            completed_tab = None
            completed_xpaths = ["//*[normalize-space()='Completed Tasks']", "//*[contains(normalize-space(), 'Completed')]", "//*[normalize-space()='완료']"]
            for xp in completed_xpaths:
                tabs = driver.find_elements(By.XPATH, xp)
                if tabs and tabs[0].is_displayed(): completed_tab = tabs[0]; break
            if completed_tab:
                robust_click(driver, completed_tab, "Completed Tab")
                wait_loading(driver)
                
            open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
            driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); time.sleep(3); check_and_switch_iframe(driver)
            row = find_matching_row(driver, item["task_name"])
            if not row and completed_tab:
                driver.get(project_url); wait_loading(driver); open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
                driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); time.sleep(3); check_and_switch_iframe(driver)
                row = find_matching_row(driver, item["task_name"])
            if not row: raise Exception("Không tìm thấy task")
            
            click_task_name_from_row(driver, row, item["task_name"])
            wait_loading(driver); check_and_switch_iframe(driver)
        
        # 🚀 TIẾP TỤC ĐOẠN ĐIỀU HƯỚNG MEMBER CHUẨN XÁC
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member'] | //button[normalize-space()='Member']"))).click()
        driver.find_element(By.CSS_SELECTOR, "button.btn-member.add[onclick='searchMemberList(3)']").click()
        
        search_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "searchId")))
        search_input.send_keys(item["col2"])
        driver.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
        cb = driver.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
        driver.execute_script("arguments[0].checked = true; driver.dispatchEvent(new Event('change', {bubbles:true}));", cb)
        driver.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=4)
        driver.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=5)

    elif run_mode == MODE_CHANGE_POINT:
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); time.sleep(3); check_and_switch_iframe(driver)
        row = find_matching_row(driver, item["task_name"])
        if not row: raise Exception("Không tìm thấy hàng dữ liệu của Task")
            
        click_task_name_from_row(driver, row, item["task_name"])
        wait_loading(driver); time.sleep(3)
        driver.switch_to.default_content() 
        
        alter_btn = None
        point_btn_selectors = ["//button[contains(@class, 'btn-s-point')]", "//button[contains(@onclick, 'Point')]", "//button[contains(normalize-space(), 'Point') or contains(normalize-space(), '점수')]"]
        for xp in point_btn_selectors:
            btns = driver.find_elements(By.XPATH, xp)
            if btns and btns[0].is_displayed(): alter_btn = btns[0]; break
        if not alter_btn:
            css_btns = driver.find_elements(By.CSS_SELECTOR, "button.btn-s-point")
            if css_btns: alter_btn = css_btns[0]
        if not alter_btn: raise Exception("Không tìm thấy nút sửa điểm số (Point Button).")
            
        robust_click(driver, alter_btn, "open point popup"); time.sleep(0.5)
        for key, val in [("#updateWorkPoint", item["anno_point"]), ("#updateReviewPoint", item["rv_point"])]:
            inp = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, key)))
            inp.click()
            driver.execute_script("arguments[0].value = '';", inp)
            inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.send_keys(str(val))
            
        driver.find_element(By.CSS_SELECTOR, "button.btn-l-point").click()
        wait_loading(driver)

    elif run_mode == MODE_3D_ANNO_REVIEW:
        progress_tab = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//li[@onclick='ingtask()']")))
        driver.execute_script("arguments[0].click();", progress_tab); wait_loading(driver)
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); time.sleep(3); check_and_switch_iframe(driver)
        row = find_matching_row(driver, item["task_name"])
        if not row: raise Exception("Không tìm thấy hàng dữ liệu")
        
        click_task_name_from_row(driver, row, item["task_name"])
        wait_loading(driver)
        
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member']"))).click()
        if item["worker_id"] and item["worker_id"].strip() not in ("-", "none", "None"):
            driver.find_element(By.CSS_SELECTOR, "button#button_WorkMember.btn-member.add[onclick*='searchMemberList(0)']").click()
            search_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "searchId")))
            search_input.send_keys(item["worker_id"])
            driver.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
            cb = driver.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
            driver.execute_script("arguments[0].checked = true; driver.dispatchEvent(new Event('change', {bubbles:true}));", cb)
            driver.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        if item["anno_limit"]:
            inp = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#workAssignCnt")))
            inp.click(); inp.send_keys(Keys.CONTROL, "a"); inp.send_keys(Keys.DELETE); inp.clear(); inp.send_keys(str(item["anno_limit"]))
        if item["reviewer_id"]:
            driver.find_element(By.CSS_SELECTOR, "button.btn-member.add[onclick*='searchMemberList(1)']").click()
            search_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "searchId")))
            search_input.send_keys(item["reviewer_id"])
            driver.find_element(By.XPATH, "//button[@onclick='searchMember()']").click(); time.sleep(1)
            cb = driver.find_element(By.CSS_SELECTOR, "#memberList input.memberChk")
            driver.execute_script("arguments[0].checked = true; driver.dispatchEvent(new Event('change', {bubbles:true}));", cb)
            driver.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
            accept_alert_if_present(driver, timeout=4)
        driver.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=5)

    elif run_mode == MODE_INSPECTION_AI:
        open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
        driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); time.sleep(3); check_and_switch_iframe(driver)
        row = find_matching_row(driver, item["task_name"])
        if row is None:
            completed_tab = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//li[contains(., 'Completed Tasks')]")))
            driver.execute_script("arguments[0].click();", completed_tab); wait_loading(driver)
            open_search_form_if_needed(driver); input_task_name(driver, item["task_name"])
            driver.find_element(By.CSS_SELECTOR, "#btn_search").click(); wait_loading(driver); time.sleep(3); check_and_switch_iframe(driver)
            row = find_matching_row(driver, item["task_name"])
        if row is None: raise Exception("Không tìm thấy task")
        
        click_task_name_from_row(driver, row, item["task_name"])
        wait_loading(driver); check_and_switch_iframe(driver)
        
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//a[normalize-space()='Member']"))).click()
        role_title = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//*[normalize-space()='Inspector']")))
        current = role_title
        for _ in range(8):
            current = current.find_element(By.XPATH, "./..")
            if "Inspector" in current.text and "Persons" in current.text: panel = current; break
        driver.execute_script("arguments[0].click();", panel.find_element(By.CSS_SELECTOR, "button.btn-member.add"))
        search_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "searchId")))
        search_input.send_keys(item["col2"])
        driver.find_element(By.XPATH, "//button[contains(., 'Search')]").click(); time.sleep(1)
        cb = driver.find_element(By.CSS_SELECTOR, "input.memberChk")
        driver.execute_script("arguments[0].checked = true; driver.dispatchEvent(new Event('change', {bubbles:true}));", cb)
        driver.find_element(By.XPATH, "//button[@onclick='addMemberSearchMember()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=4)
        driver.find_element(By.XPATH, "//button[@onclick='updateAssignCnt()']").click(); time.sleep(0.5)
        accept_alert_if_present(driver, timeout=5)

# --- PHÂN ĐOẠN ĐỌC COOKIES VÀ KÍCH HOẠT CHẠY SCRIPT ---
if st.button("🚀 KÍCH HOẠT CHẠY AUTO", type="primary"):
    if not uploaded_file or not cookie_raw:
        st.error("Vui lòng tải lên file dữ liệu (.txt) và dán chuỗi Cookies JSON trước khi chạy!")
    else:
        # 🚀 CẤU HÌNH CHROME NGẦM CHUẨN - TỐI ƯU CHO RAILWAY
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        # Giả lập để hệ thống AI Studio không quét nhận diện bot tự động
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(options=options)
        
        try:
            driver.get("https://www.ai-studio.co.kr/")
            time.sleep(1)
            driver.delete_all_cookies()
            
            cookies_list = json.loads(cookie_raw)
            for cookie in cookies_list:
                if 'sameSite' in cookie: del cookie['sameSite']
                driver.add_cookie(cookie)
                
            driver.get(project_url)
            wait_loading(driver)
            time.sleep(3)
            
            if "/login" in driver.current_url.lower():
                raise Exception("Cookies JSON dán vào đã HẾT HẠN hoặc THIẾU khóa bảo mật. Vui lòng mở Chrome máy cá nhân, bấm F5 Refresh trang AI Studio rồi tiến hành Export lại Cookies mới!")
                
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
                    
                    # 📸 BẪY ẢNH TỰ ĐỘNG: Ghi lại hình ảnh nếu dính lỗi Timeout hoặc đứng màn hình
                    if err_type == "TimeoutException" or "timeout" in error_clean.lower():
                        screenshot_path = f"error_line_{item['line_no']}.png"
                        try:
                            driver.save_screenshot(screenshot_path)
                            st.warning(f"⚠️ Phát hiện lỗi xử lý giao diện tại Dòng {item['line_no']} (Task: {item['task_name']})")
                            st.image(screenshot_path, caption=f"Ảnh chụp thực tế màn hình tại dòng lỗi {line_err}")
                        except Exception as screenshot_error:
                            st.sidebar.error(f"Không thể ghi ảnh: {screenshot_error}")
                    
                logs.append(msg)
                log_container.code("\n".join(logs))
                progress_bar.progress(idx / len(tasks))
                
            st.success("🎉 Bộ công cụ đã hoàn thành toàn bộ danh sách nhiệm vụ một cách an toàn!")
            
        except Exception as e:
            st.error(f"Lỗi hệ thống: {e}")
        finally:
            driver.quit()