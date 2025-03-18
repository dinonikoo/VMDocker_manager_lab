import streamlit as st
import requests

st.title("Управление виртуальными машинами")

# Выбор ОС
os_options = ["Ubuntu", "CentOS", "Fedora"]
os_choice = st.selectbox("Выберите ОС", os_options)

# Выбор ресурсов
cpu = st.slider("CPU", 1, 4, 2)
ram = st.slider("RAM (MB)", 512, 4096, 1024)

# Новый ползунок для выбора размера диска
disk_size = st.slider("Размер диска (GB)", 1, 100, 10)  # Мин: 1GB, Макс: 100GB, По умолчанию: 10GB
disk_format = st.selectbox("Формат диска", ["qcow2", "raw"])  # Выбор формата

# Создание ВМ
if st.button("Создать ВМ"):
    try:
        response = requests.post("http://localhost:5001/create_vm", json={
            "os": os_choice,
            "cpu": cpu,
            "ram": ram,
            "disk_size": disk_size,  # Отправляем выбранный размер диска
            "disk_format": disk_format  # Отправляем формат
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

# Получаем список ВМ с обработкой ошибок
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

# Отображение списка ВМ
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
