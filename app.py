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
st.title("🤖 AI Studio Automation Suite - Live Chrome Window Edition")

# --- KHỞI TẠO BIẾN TRẠNG THÁI PHIÊN ---
if "step" not in st.session_state:
    st.session_state.step = "setup_account"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

# --- KHỞI TẠO DRIVER HIỂN THỊ CỬA SỔ (CHẠY LOCAL) ---
if "driver" not in st.session_state or st.session_state.driver is None:
    options = webdriver.ChromeOptions()
    
    # CHÚ Ý: Bỏ hoàn toàn `--headless` và `--disable-gpu` để Chrome bật ra cửa sổ thật
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,768")
    # Giữ lại user-data-dir để lưu session login nếu cần
    options.add_argument(f"--user-data-dir=/tmp/chrome_local_window_{st.session_state.session_id}")
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(120)
    # Bật sẵn trang chủ AI-Studio lên cửa sổ mới cho bạn thao tác
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

# --- TOÀN BỘ CÁC HÀM CORE LOGIC XỬ LÝ IFRAME/GÁN TASK (GIỮ NGUYÊN BẢN CŨ CỦA BẠN) ---
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
    # [Giữ nguyên toàn bộ nội dung hàm execute_mode_logic cũ của bạn ở đây để gán task]
    pass

# =========================================================
# LUỒNG GIAO DIỆN ĐIỀU KHIỂN TRÊN STREAMLIT
# =========================================================

# BƯỚC 1: TRẠNG THÁI CHỜ USER ĐĂNG NHẬP TRÊN CỬA SỔ TRÌNH DUYỆT RIÊNG
if st.session_state.step == "setup_account":
    st.subheader("🖥️ Bước 1: Đăng nhập tài khoản")
    st.success("✨ Một cửa sổ Chrome thực tế của AI-Studio đã được mở trên máy tính của bạn!")
    st.info(
        "👉 **Bạn hãy click trực tiếp vào cửa sổ Chrome đó**, tự gõ Tên đăng nhập, Mật khẩu và mã OTP từ "
        "Google Authenticator vào như bình thường (Không lo bị hết hạn nhanh nữa).\n\n"
        "Sau khi đã vào được trang chủ bên trong thành công, hãy nhấn nút phía dưới để bắt đầu chạy Auto."
    )
    
    # Nút bấm chuyển trạng thái
    if st.button("🚀 TÔI ĐÃ ĐĂNG NHẬP XONG -> BẮT ĐẦU CHẠY AUTO", type="primary"):
        # Tự động ẩn cửa sổ Chrome xuống thanh Taskbar để tránh vướng mắt khi chạy tự động
        try: driver.minimize_window()
        except Exception: pass
        
        st.session_state.step = "auto_processing"
        st.rerun()

# BƯỚC 2: TIẾN TRÌNH CHẠY SCRIPT TỰ ĐỘNG NGẦM
elif st.session_state.step == "auto_processing":
    st.subheader("⚙️ Bước 2: Hệ thống đang xử lý tự động...")
    
    if st.button("↩️ Bật lại cửa sổ Chrome (Nếu muốn xem trực tiếp hoặc login lại)"):
        try: driver.maximize_window()
        except Exception: pass
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
                error_clean = str(e).strip().replace('\n', ' ')
                msg = f"🔴 Dòng {item['line_no']} | Lỗi dòng {line_err} ({err_type}): {error_clean[:100]} | Task: {item['task_name']}"
                
            logs.append(msg)
            log_container.code("\n".join(logs))
            progress_bar.progress(idx / len(tasks))
            
        st.success("🎉 Bộ công cụ đã hoàn thành toàn bộ danh sách nhiệm vụ!")
        try: driver.maximize_window() # Chạy xong bật lại trình duyệt lên cho bạn kiểm tra
        except Exception: pass
        
    except Exception as e:
        st.error(f"Lỗi hệ thống phát sinh: {e}")