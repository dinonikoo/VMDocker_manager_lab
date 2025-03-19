import streamlit as st
import requests

st.title("Управление виртуальными машинами")

os_options = ["Ubuntu", "ArchLinux", "Fedora"]
os_choice = st.selectbox("Выберите ОС", os_options)

cpu = st.slider("CPU", 1, 4, 2)
ram = st.slider("RAM (MB)", 512, 4096, 1024)

disk_size = st.slider("Размер диска (GB)", 1, 100, 10)  
disk_format = "qcow2" 

rental_duration = st.slider("Длительность аренды (минуты)", 1, 60, 2)  # Новый ползунок

if st.button("Создать ВМ"):
    try:
        response = requests.post("http://localhost:5001/create_vm", json={
            "os": os_choice,
            "cpu": cpu,
            "ram": ram,
            "disk_size": disk_size,  
            "disk_format": disk_format,
            "lifetime": rental_duration * 60  # Передаем длительность аренды
        })

        if response.status_code == 200:
            try:
                data = response.json()
                st.success(f"ВМ создана! Доступ по SSH: `{data['ssh']}`")
            except requests.exceptions.JSONDecodeError:
                st.error(f"Ошибка JSON! Сервер вернул: {response.text}")
        else:
            st.error(f"Ошибка {response.status_code}: {response.text}")
    
    except requests.exceptions.ConnectionError:
        st.error("Ошибка соединения! Сервер Flask не запущен.")

st.subheader("Список виртуальных машин")

try:
    response = requests.get("http://localhost:5001/list_vms")
    
    if response.status_code == 200:
        try:
            vms = response.json()
        except requests.exceptions.JSONDecodeError:
            st.error(f"Ошибка JSON! Сервер вернул: {response.text}")
            vms = []
    else:
        st.error(f"Ошибка {response.status_code}: {response.text}")
        vms = []
    
except requests.exceptions.ConnectionError:
    st.error("Ошибка соединения! Сервер Flask не запущен.")
    vms = []

if vms:
    for vm in vms:
        with st.container():
            st.write(f"**Имя:** {vm['name']} | **Порт:** {vm['port']} | **Статус:** {vm['status']}")
            st.code(f"ssh user@localhost -p {vm['port']}", language="bash")

            col1, col2, col3 = st.columns(3)
            with col1:
                if vm["status"] == "running":
                    if st.button(f"Остановить {vm['name']}"):
                        requests.post("http://localhost:5001/stop_vm", json={"name": vm["name"]})
                        st.rerun()
            with col2:
                if vm["status"] == "stopped":
                    if st.button(f"Запустить {vm['name']}"):
                        requests.post("http://localhost:5001/start_vm", json={"name": vm["name"]})
                        st.rerun()
            with col3:
                if vm["status"] == "stopped":
                    if st.button(f"Удалить {vm['name']}"):
                        requests.post("http://localhost:5001/remove_vm", json={"name": vm["name"]})
                        st.rerun()
else:
    st.write("Нет запущенных ВМ.")

