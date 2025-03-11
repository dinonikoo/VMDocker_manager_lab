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

# Кнопка запуска контейнера
if st.button("Запустить"):
    response = requests.post("http://localhost:5000/create", json={
        "type": service_type,
        "os": os_choice,
        "cpu": cpu,
        "ram": ram
    })
    st.success("Контейнер успешно запущен!")

st.subheader("Список контейнеров")

# Получаем список всех контейнеров
containers = requests.get("http://localhost:5000/list_all").json()

if containers:
    for container in containers:
        with st.container():
            st.write(f"**Имя:** {container['name']} | **Образ:** {container['image']} | **Статус:** {container['status']} | **Порты:** {container['ports']}")
            st.code(container["ssh_command"], language="bash")
            st.write(f"**Пароль:** `{container['password']}`")

            col1, col2, col3 = st.columns(3)
            with col1:
                if container["status"] == "running":
                    if st.button(f"Остановить {container['name']}"):
                        requests.post("http://localhost:5000/stop", json={"name": container['name']})
                        st.rerun()
            with col2:
                if container["status"] == "exited":
                    if st.button(f"Запустить {container['name']}"):
                        requests.post("http://localhost:5000/start", json={"name": container['name']})
                        st.rerun()
            with col3:
                if container["status"] == "exited":
                    if st.button(f"Удалить {container['name']}"):
                        requests.post("http://localhost:5000/remove", json={"name": container['name']})
                        st.rerun()
else:
    st.write("Нет контейнеров.")
