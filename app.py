import streamlit as st
import requests

st.title("Аренда виртуальных машин и контейнеров")

service_type = st.selectbox("Выберите тип сервиса", ["Виртуальная машина (QEMU)", "Контейнер (Docker)"])


os_options = {
    "Виртуальная машина (QEMU)": ["Ubuntu", "CentOS", "Fedora"],
    "Контейнер (Docker)": ["Ubuntu", "Alpine", "Nginx"]
}

os_choice = st.selectbox("Выберите ОС", os_options[service_type])

# Выбор ресурсов
cpu = st.slider("Количество CPU", 1, 4, 2)
ram = st.slider("ОЗУ (MB)", 512, 4096, 1024)

# Кнопка создания ВМ
if st.button("Создать"):
    response = requests.post("http://localhost:5000/create_vm", json={
        "type": service_type,
        "os": os_choice,
        "cpu": cpu,
        "ram": ram
    })
    data = response.json()
    st.write(f"ВМ создана! Доступ по SSH: `{data['ssh']}`")
