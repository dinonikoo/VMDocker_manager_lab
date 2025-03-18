from flask import Flask, request, jsonify
import os
import subprocess
import socket
import psutil
import json 
import time

app = Flask(__name__)
BASE_DIR = "/var/lib/qemu-vms"
os.makedirs(BASE_DIR, exist_ok=True)
vm_processes = {}  # Хранение PID запущенных ВМ


def find_free_port():
    """Находит свободный порт в системе"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def create_cloud_init_iso(vm_name):
    """Создаёт ISO-образ cloud-init"""
    cloud_init_dir = f"/tmp/cloud-init-{vm_name}"
    os.makedirs(cloud_init_dir, exist_ok=True)

    user_data = """#cloud-config
users:
  - name: user
    sudo: ["ALL=(ALL) NOPASSWD:ALL"]
    shell: /bin/bash
    lock_passwd: false
    passwd: "$6$Gbzv0TQEkpCGfXR.$l39d8Wnm8BJDKnP7PBwu.fCc2CUbje/7UFZmhngsdA5IxrusHmyUpUVYh5S8bkDmhT4G0suRXNfz8fzOJ.cvZ/"
chpasswd:
  expire: false
ssh_pwauth: true

packages:
  - openssh-server
  - net-tools

runcmd:
  - systemctl restart ssh
  - systemctl enable ssh
"""
    
    meta_data = f"instance-id: {vm_name}\nlocal-hostname: {vm_name}"
    
    with open(f"{cloud_init_dir}/user-data", "w") as f:
        f.write(user_data)
    with open(f"{cloud_init_dir}/meta-data", "w") as f:
        f.write(meta_data)
    
    iso_path = f"/tmp/{vm_name}-cloud-init.iso"
    subprocess.run([
        "genisoimage", "-output", iso_path, "-volid", "CIDATA",
        "-joliet", "-rock", f"{cloud_init_dir}/user-data", f"{cloud_init_dir}/meta-data"
    ])
    
    return iso_path


def create_vm(name, os_choice, cpu, ram, disk_size, disk_format="qcow2"):
    cloud_images = {
        "Ubuntu": "/var/lib/libvirt/images/ubuntu-cloud.qcow2",
        "ArchLinux": "/var/lib/libvirt/images/Arch-Linux-x86_64-cloudimg.qcow2",
        "Fedora": "/var/lib/libvirt/images/fedora.qcow2"
    }
    base_image = cloud_images.get(os_choice, cloud_images["Ubuntu"])
    disk_path = f"{BASE_DIR}/{name}.{disk_format}"

    if disk_format == "qcow2":
        subprocess.run(["qemu-img", "create", "-f", "qcow2", "-b", base_image, disk_path, "-F", "qcow2"])
        subprocess.run(["qemu-img", "resize", disk_path, f"{disk_size}G"])
    elif disk_format == "raw":
        subprocess.run(["qemu-img", "convert", "-f", "qcow2", "-O", "raw", base_image, disk_path])
        subprocess.run(["qemu-img", "resize", disk_path, f"{disk_size}G"])

    cloud_init_iso = create_cloud_init_iso(name)
    ssh_port = find_free_port()
    qmp_socket = f"/tmp/{name}-qmp.sock"

    qemu_cmd = [
        "qemu-system-x86_64",
        "-cpu", "qemu64",
        "-m", str(ram),
        "-smp", str(cpu),
        "-drive", f"file={disk_path},format={disk_format}",
        "-drive", f"file={cloud_init_iso},media=cdrom",
        "-net", f"user,hostfwd=tcp::{ssh_port}-:22",
        "-net", "nic",
        "-qmp", f"unix:{qmp_socket},server,nowait"
    ]

    process = subprocess.Popen(qemu_cmd)
    vm_processes[name] = {"pid": process.pid, "port": ssh_port, "qmp_socket": qmp_socket}

    return {
        "message": f"ВМ {name} создана!",
        "ssh": f"ssh user@localhost -p {ssh_port} (пароль: 12345)",
        "port": ssh_port
    }


@app.route("/create_vm", methods=["POST"])
def api_create_vm():
    """Создание ВМ через API с указанием дискового пространства"""
    try:
        data = request.json
        name = f"vm-{data['os'].lower()}-{data['cpu']}cpu-{data['ram']}mb"

        disk_size = data.get("disk_size", 10)  # Если нет в запросе, ставим 10GB
        disk_format = data.get("disk_format", "qcow2")  # По умолчанию qcow2

        result = create_vm(name, data["os"], data["cpu"], data["ram"], disk_size, disk_format)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/list_vms", methods=["GET"])
def list_vms():
    """Возвращает список всех ВМ (запущенных и остановленных)"""
    vms = {}

    # Проверяем файлы виртуальных дисков
    for filename in os.listdir(BASE_DIR):
        if filename.endswith(".qcow2") or filename.endswith(".raw"):
            name = filename.split(".")[0]
            vms[name] = {
                "name": name,  # Добавляем имя ВМ
                "status": "stopped",
                "disk": os.path.join(BASE_DIR, filename),
                "port": None  # Порт не нужен для остановленных ВМ
            }

    # Проверяем запущенные процессы
    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        if "qemu-system" in " ".join(proc.info["cmdline"] or []):
            for name in vms:
                if name in " ".join(proc.info["cmdline"]):
                    vms[name]["status"] = "running"
                    vms[name]["pid"] = proc.info["pid"]
                    vms[name]["port"] = vm_processes.get(name, {}).get("port", "Unknown")  # Добавляем порт, если известен

    return jsonify(list(vms.values()))




def send_qmp_command(socket_path, command):
    """Отправляет команду в QMP сокет"""
    try:
        if not os.path.exists(socket_path):
            print(f"[Ошибка] QMP сокет {socket_path} не найден!")
            return False

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(socket_path)

            # Получаем приветственное сообщение от QEMU
            welcome_message = s.recv(1024).decode()
            print(f"[QMP Приветствие] {welcome_message}")

            # Отправляем команду активации QMP
            qmp_capabilities = json.dumps({"execute": "qmp_capabilities"})
            print(f"[Отправка QMP Capabilities] {qmp_capabilities}")
            s.sendall(qmp_capabilities.encode() + b"\n")
            time.sleep(1)

            response = s.recv(1024).decode()
            print(f"[Ответ QMP Capabilities] {response}")

            # Отправляем реальную команду
            cmd = json.dumps({"execute": command})
            print(f"[Отправка команды] {cmd}")
            s.sendall(cmd.encode() + b"\n")
            time.sleep(1)

            response = s.recv(1024).decode()
            print(f"[Ответ QMP] {response}")

            return "return" in response  # Проверяем, что QEMU отработал команду
    except Exception as e:
        print(f"[Ошибка QMP] {e}")
        return False


@app.route("/stop_vm", methods=["POST"])
def stop_vm():
    data = request.json
    name = data["name"]

    if name in vm_processes:
        qmp_socket = vm_processes[name]["qmp_socket"]
        if send_qmp_command(qmp_socket, "system_powerdown"):
            return jsonify({"status": "stopped", "name": name})
        else:
            return jsonify({"error": "Не удалось остановить ВМ"}), 500
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
