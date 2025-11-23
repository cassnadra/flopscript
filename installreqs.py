import subprocess
import sys
import time

DEPENDENCIES = [
    "requests",
    "pillow",
]

def banner(text):
    print("\n" + "=" * 50)
    print(text)
    print("=" * 50 + "\n")

def install_package(pkg):
    banner(f"Installing: {pkg}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        print(f"[OK] Installed: {pkg}")
    except subprocess.CalledProcessError:
        print(f"[ERROR] Install failed: {pkg}")

def check_pip():
    banner("Checking pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"])
        print("pip found.\n")
    except:
        print("pip not found. Attempting to install using ensurepip...\n")
        try:
            subprocess.check_call([sys.executable, "-m", "ensurepip"])
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        except:
            print("pip installation failed. Install Python from python.org with pip enabled.")
            sys.exit(1)

def main():
    banner("FloppyTracker Dependency Installer")
    check_pip()

    print("The following packages will be installed:\n")
    for pkg in DEPENDENCIES:
        print(f" - {pkg}")

    cont = input("\nContinue? [y/N]: ").strip().lower()
    if cont != "y":
        print("\nCancelled.")
        sys.exit(0)

    for pkg in DEPENDENCIES:
        install_package(pkg)
        time.sleep(0.5)

    banner("DONE")
    print("All required dependencies are installed.\n")
    print("You may now run your tracking script.\n")

if __name__ == "__main__":
    main()
