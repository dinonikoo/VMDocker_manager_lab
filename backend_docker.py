from flask import Flask, request, jsonify
import subprocess
import socket
import json
import secrets

app = Flask(__name__)

DOCKERFILES = {
    "Ubuntu": "Dockerfile.ubuntu",
    "Alpine": "Dockerfile.alpine",
    "Debian": "Dockerfile.debian"
}

container_passwords = {}  #passwords


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


@app.route('/create', methods=['POST'])
def create_instance():
    data = request.json
    container_name = f"{data['os'].lower()}_{find_free_port()}"
    ssh_port = find_free_port()
    password = secrets.token_urlsafe(12)  

    if data['os'] in DOCKERFILES:
        image = f"{data['os'].lower()}_custom"
        dockerfile_path = f"./dockerfiles/{DOCKERFILES[data['os']]}"

        subprocess.run(f"docker build -t {image} -f {dockerfile_path} ./dockerfiles", shell=True, check=True)

        subprocess.run(
            f"docker run -dit --name {container_name} -p {ssh_port}:22 --cpus={data['cpu']} --memory={data['ram']}m {image}",
            shell=True, check=True)

        if data["os"] == "Alpine":
            subprocess.run(f"docker exec {container_name} sh -c \"echo 'root:{password}' | chpasswd\"", shell=True, check=True)
        else:
            subprocess.run(f"docker exec {container_name} bash -c \"echo 'root:{password}' | chpasswd\"", shell=True, check=True)

        container_passwords[container_name] = {"password": password, "ssh_port": ssh_port}

        return jsonify({"status": "Контейнер успешно запущен"})
    else:
        return jsonify({"status": "Ошибка", "details": "Неизвестная ОС"})


@app.route('/list_all', methods=['GET'])
def list_all_containers():
    cmd = "docker ps -a --format '{{json .}}'"
    output = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    containers = [json.loads(line) for line in output.stdout.splitlines()]

    result = []
    for container in containers:
        name = container["Names"]

        if name in container_passwords:
            ssh_port = container_passwords[name]["ssh_port"]
            password = container_passwords[name]["password"]
        else:
            ssh_port = "Не найдено"
            password = "Не найдено"

        result.append({
            "name": name,
            "image": container["Image"],
            "status": container["State"],
            "ports": container["Ports"],
            "ssh_command": f"ssh root@localhost -p {ssh_port}" if ssh_port != "Не найдено" else "SSH не настроен",
            "password": password
        })

    return jsonify(result)


@app.route('/start', methods=['POST'])
def start_container():
    data = request.json
    container_name = data['name']

    subprocess.run(f"docker start {container_name}", shell=True, check=True)
    return jsonify({"status": "Контейнер запущен", "container": container_name})


@app.route('/stop', methods=['POST'])
def stop_container():
    data = request.json
    container_name = data['name']

    subprocess.run(f"docker stop {container_name}", shell=True, check=True)
    return jsonify({"status": "Контейнер остановлен", "container": container_name})


@app.route('/remove', methods=['POST'])
def remove_container():
    data = request.json
    container_name = data['name']

    subprocess.run(f"docker rm {container_name}", shell=True, check=True)

    if container_name in container_passwords:
        del container_passwords[container_name]

    return jsonify({"status": "Контейнер удален", "container": container_name})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
