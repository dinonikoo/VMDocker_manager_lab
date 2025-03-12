from flask import Flask, request, jsonify
import os
import subprocess
import socket
import psutil

app = Flask(__name__)
BASE_DIR = "/var/lib/qemu-vms"
os.makedirs(BASE_DIR, exist_ok=True)
vm_processes = {}  # Хранение PID запущенных ВМ


def find_free_port():
    """Находит свободный порт в системе"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def create_vm(name, os_choice, cpu, ram):
    """Создаёт виртуальную машину QEMU"""
    cloud_images = {
        "Ubuntu": "/var/lib/libvirt/images/ubuntu-cloud.qcow2",
        "Fedora": "/var/lib/libvirt/images/fedora.qcow2",
        "CentOS": "/var/lib/libvirt/images/centos.qcow2"
    }
    base_image = cloud_images.get(os_choice, cloud_images["Ubuntu"])

    disk_path = f"{BASE_DIR}/{name}.qcow2"
    subprocess.run(["qemu-img", "create", "-f", "qcow2", "-b", base_image, disk_path, "-F", "qcow2"])

    ssh_port = find_free_port()
    qemu_cmd = [
        "qemu-system-x86_64",
        "-cpu", "qemu64",
        "-m", str(ram),
        "-smp", str(cpu),
        "-drive", f"file={disk_path},format=qcow2",
        "-net", f"user,hostfwd=tcp::{ssh_port}-:22",
        "-net", "nic"
    ]

    process = subprocess.Popen(qemu_cmd)
    vm_processes[name] = {"pid": process.pid, "port": ssh_port}

    return {
        "message": f"ВМ {name} создана!",
        "ssh": f"ssh user@localhost -p {ssh_port} (пароль: 12345)",
        "port": ssh_port
    }


@app.route("/create_vm", methods=["POST"])
def api_create_vm():
    """Создание ВМ через API"""
    data = request.json
    name = f"vm-{data['os'].lower()}-{data['cpu']}cpu-{data['ram']}mb"
    result = create_vm(name, data["os"], data["cpu"], data["ram"])
    return jsonify(result)


@app.route("/list_vms", methods=["GET"])
def list_vms():
    """Получает список запущенных ВМ"""
    vms = []
    for name, info in vm_processes.items():
        if psutil.pid_exists(info["pid"]):
            vms.append({"name": name, "port": info["port"], "status": "running"})
        else:
            vms.append({"name": name, "port": info["port"], "status": "stopped"})

    return jsonify(vms)


@app.route("/stop_vm", methods=["POST"])
def stop_vm():
    """Останавливает ВМ по имени"""
    data = request.json
    name = data["name"]

    if name in vm_processes:
        pid = vm_processes[name]["pid"]
        os.kill(pid, 9)
        return jsonify({"status": "stopped", "name": name})
    else:
        return jsonify({"error": "ВМ не найдена"}), 404


@app.route("/remove_vm", methods=["POST"])
def remove_vm():
    """Удаляет ВМ (должна быть остановлена)"""
    data = request.json
    name = data["name"]

    disk_path = f"{BASE_DIR}/{name}.qcow2"
    if os.path.exists(disk_path):
        os.remove(disk_path)

    if name in vm_processes:
        del vm_processes[name]

    return jsonify({"status": "removed", "name": name})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
