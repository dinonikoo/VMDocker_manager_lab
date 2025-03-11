import streamlit as st
import requests

st.title("Аренда виртуальных машин и контейнеров")

# Выбор типа сервиса
service_type = st.selectbox("Выберите тип сервиса", ["Виртуальная машина (QEMU)", "Контейнер (Docker)"])

# Выбор ОС
os_options = {
    "Виртуальная машина (QEMU)": ["Ubuntu", "Debian", "CentOS"],
    "Контейнер (Docker)": ["Ubuntu", "Alpine", "Debian"]
}
os_choice = st.selectbox("Выберите ОС", os_options[service_type])

# Выбор ресурсов
cpu = st.slider("CPU", 1, 4, 2)
ram = st.slider("RAM (MB)", 512, 4096, 1024)

# Кнопка запуска
if st.button("Запустить"):
    response = requests.post("http://localhost:5000/create", json={
        "type": service_type,
        "os": os_choice,
        "cpu": cpu,
        "ram": ram
    })
    st.write(response.json())
