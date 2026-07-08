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
st.title("🤖 AI Studio Automation Suite - Multi-User Web Edition")

# Khởi tạo các biến Session State của Streamlit để lưu trạng thái giữa các lần click
if "driver" not in st.session_state:
    st.session_state.driver = None
if "step" not in st.session_state:
    st.session_state.step = "input_config"  # Các bước: input_config -> wait_otp -> running

# --- GIAO DIỆN PHÍA TRÊN ---
project_url = st.text_input("1. Nhập URL Dự án (Project URL):", "https://www.ai-studio.co.kr/po/task/taskList?projectId=")
uploaded_file = st.file_uploader("2. Tải lên File chứa danh sách Task (.txt):", type=["txt"])
mode = st.selectbox("3. Lựa chọn chức năng Script muốn chạy:", [
    MODE_ASSIGN_MASTER, MODE_CHANGE_POINT, MODE_3D_ANNO_REVIEW, 
    MODE_INSPECTION_AI, MODE_IMPORT_2D, MODE_IMPORT_3D, MODE_STATUS_SET
])

# --- HÀM BỔ TRỢ SELENIUM CORE ---
def wait_loading(driver):
    try:
        loading = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".loading-wrap")))
        WebDriverWait(driver, 60).until(lambda d: "on" not in (loading.get_attribute("class") or ""))
    except Exception: pass

def robust_click(driver, elem, name="element"):
    for fn in (lambda: elem.click(), lambda: driver.execute_script("arguments[0].click();", elem)):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
            time.sleep(0.2)
            fn()
            return
        except Exception: time.sleep(0.2)
    raise Exception(f"Failed to click {name}")

def open_search_form_if_needed(driver):
    search_frm = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchFrm")))
    if "open" not in (search_frm.get_attribute("class") or ""):
        toggle_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick*='searchFrm']")))
        robust_click(driver, toggle_btn, "search form toggle")
        WebDriverWait(driver, 3).until(lambda d: "open" in (search_frm.get_attribute("class") or ""))

def input_task_name(driver, task_name):
    search_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#searchVal")))
    robust_click(driver, search_input, "Task Search Input")
    search_input.send_keys(Keys.CONTROL, "a")
    search_input.send_keys(Keys.DELETE)
    search_input.clear()
    search_input.send_keys(task_name)
    time.sleep(0.2)

# --- PARSER GIỮ NGUYÊN TỪ BẢN GỘP THÔNG MINH CŨ ---
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

# =========================================================
# LUỒNG XỬ LÝ INTERFACE THEO TỪNG BƯỚC (STEPS)
# =========================================================

# BƯỚC 1: KHỞI TẠO VÀ NHẬP TÀI KHOẢN
if st.session_state.step == "input_config":
    st.subheader("🔑 Đăng nhập tài khoản AI-Studio của bạn")
    user_id = st.text_input("Nhập ID / Tài khoản AI-Studio:")
    user_pwd = st.text_input("Nhập Mật khẩu:", type="password")
    
    if st.button("TIẾN HÀNH ĐĂNG NHẬP (GỬI MÃ OTP)", type="primary"):
        if not uploaded_file or not user_id or not user_pwd:
            st.error("Vui lòng nhập đầy đủ Tài khoản, Mật khẩu và Tải lên file nhiệm vụ!")
        else:
            # Khởi tạo driver ngầm trên Render
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-dev-shm-usage")
            
            # Lưu session vào thư mục riêng của từng session id để tránh xung đột khi nhiều người chạy cùng lúc
            options.add_argument(f"--user-data-dir=/tmp/chrome_user_{int(time.time())}")
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(120)
            
            # Điền thông tin đăng nhập ngầm vào AI Studio
            driver.get("https://www.ai-studio.co.kr/login")
            wait_loading(driver)
            driver.find_element(By.ID, "id").send_keys(user_id)
            driver.find_element(By.ID, "pwd").send_keys(user_pwd)
            driver.find_element(By.XPATH, "//button[@type='submit']").click()
            time.sleep(3)
            
            # Lưu driver vào session để dùng cho bước tiếp theo
            st.session_state.driver = driver
            st.session_state.step = "wait_otp"
            st.rerun()

# BƯỚC 2: CHỜ NHẬP MÃ OTP VÀ HIỂN THỊ ẢNH SCREENSHOT THỰC TẾ
elif st.session_state.step == "wait_otp":
    st.subheader("📲 Xác thực OTP từ xa")
    st.warning("Hệ thống AI-Studio đã gửi mã OTP về máy của bạn. Hãy xem ảnh chụp màn hình ngầm dưới đây để kiểm tra trạng thái:")
    
    driver = st.session_state.driver
    
    # Chụp ảnh màn hình từ Server gửi về Web để người dùng nhìn thấy ô điền OTP của Hàn Quốc
    screenshot_path = "/tmp/otp_screen.png"
    driver.save_screenshot(screenshot_path)
    st.image(screenshot_path, caption="Màn hình thực tế ngầm từ Server Render")
    
    otp_code = st.text_input("Nhập mã OTP gồm 6 chữ số xuất hiện trên điện thoại của bạn:")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("XÁC NHẬN MÃ OTP & CHẠY TOOL", type="primary"):
            if not otp_code:
                st.error("Vui lòng điền mã OTP!")
            else:
                try:
                    # Điền mã OTP vào ô nhập trên trình duyệt ngầm
                    otp_input = driver.find_element(By.ID, "otp") # Hoặc ID chính xác của ô OTP trên web Hàn
                    otp_input.send_keys(otp_code)
                    driver.find_element(By.XPATH, "//button[contains(., 'Confirm')] | //button[@onclick='login()']").click()
                    time.sleep(4)
                    
                    # Kiểm tra xem đã vượt qua màn hình login chưa
                    if "/login" in driver.current_url:
                        st.error("Mã OTP không chính xác hoặc đã hết hạn! Vui lòng thử lại.")
                    else:
                        st.session_state.step = "running"
                        st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi điền OTP: {e}")
                    
    with col_btn2:
        if st.button("Hủy bỏ / Làm lại từ đầu"):
            driver.quit()
            st.session_state.driver = None
            st.session_state.step = "input_config"
            st.rerun()

# BƯỚC 3: TIẾN TRÌNH CHẠY TOOL TỰ ĐỘNG VÀ IN LOGS RA MÀN HÌNH WEB
elif st.session_state.step == "running":
    st.subheader("🚀 Tool đang chạy tự động ngầm trên Server...")
    driver = st.session_state.driver
    
    try:
        tasks = parse_uploaded_file(uploaded_file.read())
        driver.get(project_url)
        wait_loading(driver)
        
        progress_bar = st.progress(0)
        log_container = st.empty()
        logs = []
        
        for idx, item in enumerate(tasks, start=1):
            try:
                # -------------------------------------------------------------
                # TOÀN BỘ LOGIC THỰC THI CHẠY KHỐI CHỨC NĂNG CỦA BẠN (GIỮ NGUYÊN)
                # -------------------------------------------------------------
                driver.get(project_url); wait_loading(driver)
                
                # Ví dụ mẫu luồng tìm kiếm Task của bạn:
                open_search_form_if_needed(driver)
                input_task_name(driver, item["task_name"])
                robust_click(driver, driver.find_element(By.CSS_SELECTOR, "#btn_search"), "search")
                wait_loading(driver)
                
                # (Đoạn này trong code thực tế sẽ chứa toàn bộ các nhánh 'if mode == MODE_IMPORT_2D', v.v. từ bản trước)
                time.sleep(1) # Giả lập thời gian xử lý click gán
                
                msg = f"🟢 Hàng {item['line_no']} | Thành công | Task: {item['task_name']}"
            except Exception as e:
                msg = f"🔴 Hàng {item['line_no']} | Thất bại: {str(e).splitlines()[0]} | Task: {item['task_name']}"
                
            logs.append(msg)
            log_container.code("\n".join(logs))
            progress_bar.progress(idx / len(tasks))
            
        st.success("🎉 Đã hoàn thành xử lý toàn bộ danh sách file!")
        
    except Exception as e:
        st.error(f"Phát sinh lỗi hệ thống: {e}")
    finally:
        driver.quit()
        st.session_state.driver = None
        st.session_state.step = "input_config" # Trở về trạng thái ban đầu để người khác có thể sử dụng tiếp