from flask import Flask, request, jsonify
import os
import subprocess
import socket
import psutil
import json 
import time
import threading

app = Flask(__name__)
BASE_DIR = "/var/lib/qemu-vms"
os.makedirs(BASE_DIR, exist_ok=True)
vm_processes = {}  
vm_lifetime = {}  # Время жизни ВМ (в секундах)
vm_end_time = {}  # Время, когда ВМ должна завершить работу
active_timers = {}  # Активные таймеры

def wait_for_ssh(port, timeout=60, initial_delay=40):
    time.sleep(initial_delay) 
    start_time = time.time()
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(("localhost", port)) == 0:
                return True
        time.sleep(1) 
    return False

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]
    
def send_qmp_command(socket_path, command):
    try:
        if not os.path.exists(socket_path):
            print(f"[Ошибка] QMP сокет {socket_path} не найден!")
            return False

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(socket_path)

            welcome_message = s.recv(1024).decode()
            print(f"[QMP Приветствие] {welcome_message}")

            qmp_capabilities = json.dumps({"execute": "qmp_capabilities"})
            print(f"[Отправка QMP Capabilities] {qmp_capabilities}")
            s.sendall(qmp_capabilities.encode() + b"\n")
            time.sleep(1)

            response = s.recv(1024).decode()
            print(f"[Ответ QMP Capabilities] {response}")

            cmd = json.dumps({"execute": command})
            print(f"[Отправка команды] {cmd}")
            s.sendall(cmd.encode() + b"\n")
            time.sleep(1)

            response = s.recv(1024).decode()
            print(f"[Ответ QMP] {response}")

            return "return" in response 
    except Exception as e:
        print(f"[Ошибка QMP] {e}")
        return False

def stop_vm_directly(vm_name):
    if vm_name in vm_processes:
        qmp_socket = vm_processes[vm_name]["qmp_socket"]
        if send_qmp_command(qmp_socket, "system_powerdown"):
            print(f"ВМ {vm_name} остановлена.")
            return True
    return False
    
def stop_vm_when_time_expires(vm_name):
    while vm_name in vm_end_time:
        remaining_time = max(0, vm_end_time[vm_name] - time.time())
        if remaining_time <= 0:
            if stop_vm_directly(vm_name):  
                print(f"ВМ {vm_name} автоматически остановлена.")
            else:
                print(f"Ошибка: не удалось остановить ВМ {vm_name}.")
            del vm_end_time[vm_name]
            break
        time.sleep(1)

def save_vm_config(name, config):
    config_path = os.path.join(BASE_DIR, f"{name}.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

def load_vm_config(name):
    config_path = os.path.join(BASE_DIR, f"{name}.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return None

def create_cloud_init_iso(vm_name):
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


def create_vm(name, os_choice, cpu, ram, disk_size, disk_format="qcow2", lifetime=180):
    cloud_images = {
        "Ubuntu": "/var/lib/libvirt/images/ubuntu-cloud.qcow2",
        "ArchLinux": "/var/lib/libvirt/images/Arch-Linux-x86_64-cloudimg.qcow2",
        "Fedora": "/var/lib/libvirt/images/fedora.qcow2"
    }
    base_image = cloud_images.get(os_choice, cloud_images["Ubuntu"])
    disk_path = f"{BASE_DIR}/{name}.{disk_format}"

    subprocess.run(["qemu-img", "create", "-f", "qcow2", "-b", base_image, disk_path, "-F", "qcow2"])
    subprocess.run(["qemu-img", "resize", disk_path, f"{disk_size}G"])

    cloud_init_iso = create_cloud_init_iso(name)
    ssh_port = find_free_port()
    qmp_socket = f"/tmp/{name}-qmp.sock"

    config = {
        "name": name,
        "os": os_choice,
        "cpu": cpu,
        "ram": ram,
        "disk_size": disk_size,
        "disk_format": disk_format,
        "port": ssh_port,
        "qmp_socket": qmp_socket
    }
    save_vm_config(name, config)

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
    vm_lifetime[name] = lifetime
    vm_end_time[name] = time.time() + lifetime
 
    timer_thread = threading.Thread(target=stop_vm_when_time_expires, args=(name,), daemon=True)
    timer_thread.start()
    active_timers[name] = timer_thread
    
    if wait_for_ssh(ssh_port):
        return {
            "message": f"ВМ {name} создана!",
            "ssh": f"ssh user@localhost -p {ssh_port} (пароль: 12345)",
            "port": ssh_port,
            "lifetime": lifetime
        }
    else:
        return {
            "message": f"ВМ {name} создана, но SSH не доступен через 60 секунд",
            "port": ssh_port
        }


@app.route("/create_vm", methods=["POST"])
def api_create_vm():
    try:
        data = request.json
        name = f"vm-{data['os'].lower()}-{data['cpu']}cpu-{data['ram']}mb"
        lifetime = data.get("lifetime", 180) 
        result = create_vm(name, data["os"], data["cpu"], data["ram"], data.get("disk_size", 10), data.get("disk_format", "qcow2"))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/list_vms", methods=["GET"])
def list_vms():
    vms = {}
 
    for filename in os.listdir(BASE_DIR):
        if filename.endswith(".qcow2"):
            name = filename.split(".")[0]
            vms[name] = {
                "name": name,  
                "status": "stopped",
                "disk": os.path.join(BASE_DIR, filename),
                "port": None,
                "remaining_time": None
            }
 
    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        cmdline = " ".join(proc.info["cmdline"] or [])
        if "qemu-system" in cmdline:
            for name in vms:
                if name in cmdline:
                    vms[name]["status"] = "running"
                    vms[name]["pid"] = proc.info["pid"]
                    vms[name]["port"] = vm_processes.get(name, {}).get("port", "Unknown")
                if name in vm_end_time:
                    remaining_time = max(0, int(vm_end_time[name] - time.time()))
                    vms[name]["remaining_time"] = remaining_time
                else:
                    vms[name]["remaining_time"] = None

    for name, process in vm_processes.items():
        if name not in vms:
            vms[name] = {
                "name": name,
                "status": "running",
                "port": process["port"],
                "remaining_time": max(0, int(vm_end_time.get(name, 0) - time.time())) if name in vm_end_time else None
            }
    return jsonify(list(vms.values()))


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


@app.route("/start_vm", methods=["POST"])
def start_vm():
    try:
        data = request.json
        name = data["name"]
        config = load_vm_config(name)
        
        if not config:
            return jsonify({"error": "Конфигурация ВМ не найдена"}), 404
        
        ssh_port = find_free_port()
        config["port"] = ssh_port
        save_vm_config(name, config)
        
        qemu_cmd = [
            "qemu-system-x86_64",
            "-cpu", "qemu64",
            "-m", str(config["ram"]),
            "-smp", str(config["cpu"]),
            "-drive", f"file={BASE_DIR}/{name}.{config['disk_format']},format={config['disk_format']}",
            "-net", f"user,hostfwd=tcp::{ssh_port}-:22",
            "-net", "nic",
            "-qmp", f"unix:{config['qmp_socket']},server,nowait"
        ]
        process = subprocess.Popen(qemu_cmd)
        vm_processes[name] = {"pid": process.pid, "port": ssh_port, "qmp_socket": config["qmp_socket"]}
        vm_end_time[name] = time.time() + vm_lifetime.get(name, 180)# ДОБАВЛЕНА
        if name not in active_timers or not active_timers[name].is_alive(): # ДОБАВЛЕНА
            timer_thread = threading.Thread(target=stop_vm_when_time_expires, args=(name,), daemon=True) # ДОБАВЛЕНА
            timer_thread.start() # ДОБАВЛЕНА
            active_timers[name] = timer_thread # ДОБАВЛЕНА
        return jsonify({
            "message": f"ВМ {name} запущена!",
            "ssh": f"ssh user@localhost -p {ssh_port}",
            "port": ssh_port
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/remove_vm", methods=["POST"])
def remove_vm():
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
