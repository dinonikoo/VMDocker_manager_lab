import streamlit as st
import requests

st.title("Управление виртуальными машинами")

# Выбор ОС
os_options = ["Ubuntu", "CentOS", "Fedora"]
os_choice = st.selectbox("Выберите ОС", os_options)

# Выбор ресурсов
cpu = st.slider("CPU", 1, 4, 2)
ram = st.slider("RAM (MB)", 512, 4096, 1024)

# Создание ВМ
if st.button("Создать ВМ"):
    response = requests.post("http://localhost:5001/create_vm", json={
        "os": os_choice,
        "cpu": cpu,
        "ram": ram
    })
    if response.status_code == 200:
        data = response.json()
        st.success(f"ВМ создана! Доступ по SSH: `{data['ssh']}`")
    else:
        st.error(f"Ошибка: {response.json().get('error', 'Неизвестная ошибка')}")

st.subheader("Список виртуальных машин")

# Получаем список ВМ
vms = requests.get("http://localhost:5001/list_vms").json()

if vms:
    for vm in vms:
        with st.container():
            st.write(f"**Имя:** {vm['name']} | **Порт:** {vm['port']} | **Статус:** {vm['status']}")
            st.code(f"ssh user@localhost -p {vm['port']}", language="bash")

            col1, col2 = st.columns(2)
            with col1:
                if vm["status"] == "running":
                    if st.button(f"Остановить {vm['name']}"):
                        requests.post("http://localhost:5001/stop_vm", json={"name": vm["name"]})
                        st.rerun()
            with col2:
                if vm["status"] == "stopped":
                    if st.button(f"Удалить {vm['name']}"):
                        requests.post("http://localhost:5001/remove_vm", json={"name": vm["name"]})
                        st.rerun()
else:
    st.write("Нет запущенных ВМ.")

# Кнопка возврата
if st.button("Назад"):
    st.switch_page("one.py")
