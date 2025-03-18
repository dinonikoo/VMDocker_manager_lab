import streamlit as st
import requests

st.title("Управление контейнерами (Docker)")

os_choice = st.selectbox("Выберите ОС", ["Ubuntu", "Alpine", "Debian"])
cpu = st.slider("CPU", 1, 4, 2)
ram = st.slider("RAM (MB)", 512, 4096, 1024)
lifetime = st.slider("Время жизни контейнера (минуты)", 1, 60, 10)  # От 1 до 60 минут

if st.button("Запустить контейнер"):
    response = requests.post("http://localhost:5000/create", json={
        "os": os_choice,
        "cpu": cpu,
        "ram": ram,
        "lifetime": lifetime
    })
    st.success("Контейнер успешно запущен!")

st.subheader("Список контейнеров")

containers = requests.get("http://localhost:5000/list_all").json()

if containers:
    for container in containers:
        with st.container():
            st.write(f"**Имя:** {container['name']} | **Образ:** {container['image']} | **Статус:** {container['status']} | **Порты:** {container['ports']}")
            st.code(container["ssh_command"], language="bash")
            st.write(f"**Пароль:** `{container['password']}`")

            # Вывод времени только если контейнер работает
            if container.get("remaining_time") is not None:
                st.write(f"⏳ Оставшееся время: {container['remaining_time']} сек.")

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
    st.write("Нет активных контейнеров.")
