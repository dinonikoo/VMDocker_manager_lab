from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

DOCKERFILES = {
    "Ubuntu": "Dockerfile.ubuntu",
    "Alpine": "Dockerfile.alpine",
    "Debian": "Dockerfile.debian"
}


@app.route('/create', methods=['POST'])
def create_instance():
    data = request.json
    container_name = data['os'].lower()
    ssh_port = 2223  # TODO: Динамическое назначение порта

    if data['os'] in DOCKERFILES:
        image = f"{data['os'].lower()}_custom"
        dockerfile_path = f"./dockerfiles/{DOCKERFILES[data['os']]}"

        # Проверка существования образа
        cmd_build = f"docker build -t {image} -f {dockerfile_path} ./dockerfiles"
        subprocess.run(cmd_build, shell=True, check=True)

        # Запуск контейнера с OpenSSH
        cmd_run = f"docker run -it --name {container_name} -p {ssh_port}:22 --cpus={data['cpu']} --memory={data['ram']}m {image}"
        subprocess.run(cmd_run, shell=True, check=True)

        return jsonify({"status": "Запущено", "details": cmd_run})

    else:
        return jsonify({"status": "Ошибка", "details": "Неизвестная ОС"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
