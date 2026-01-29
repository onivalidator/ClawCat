#!/usr/bin/env python3
"""Service installation helper for ClawCat."""

import subprocess
import sys
from pathlib import Path


def check_admin():
    """Check if running with admin privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_python_path():
    """Get the path to the Python executable."""
    return sys.executable


def get_service_script():
    """Get the path to the service script."""
    return str(Path(__file__).parent / "clawcat" / "service.py")


def install_service():
    """Install the ClawCat Windows service."""
    print("ClawCat Service Installer")
    print("=" * 50)
    print()

    if not check_admin():
        print("ERROR: Administrator privileges required!")
        print()
        print("Please run this script as Administrator:")
        print("  1. Open Command Prompt as Administrator")
        print("  2. Navigate to the ClawCat directory")
        print("  3. Run: python install_service.py")
        return False

    python_path = get_python_path()
    service_script = get_service_script()

    print(f"Python: {python_path}")
    print(f"Service script: {service_script}")
    print()

    # Check if config exists
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print("WARNING: config.yaml not found!")
        print("The service will fail to start without configuration.")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Installation cancelled.")
            return False

    print("Installing service...")

    try:
        # Install the service
        result = subprocess.run(
            [python_path, service_script, "install"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("Service installed successfully!")
            print()

            # Configure service to auto-start
            print("Configuring auto-start...")
            subprocess.run(
                ["sc", "config", "ClawCat", "start=", "auto"],
                capture_output=True
            )

            print()
            print("Service commands:")
            print("  Start:   net start ClawCat")
            print("  Stop:    net stop ClawCat")
            print("  Remove:  python install_service.py --remove")
            print()
            print("Logs: C:\\Users\\kevin\\ClaudeLogs\\clawcat-service.log")

            # Ask to start now
            print()
            response = input("Start the service now? (y/n): ")
            if response.lower() == 'y':
                subprocess.run(["net", "start", "ClawCat"])

            return True
        else:
            print(f"Installation failed!")
            print(f"Error: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def remove_service():
    """Remove the ClawCat Windows service."""
    print("Removing ClawCat service...")

    if not check_admin():
        print("ERROR: Administrator privileges required!")
        return False

    python_path = get_python_path()
    service_script = get_service_script()

    try:
        # Stop service first
        subprocess.run(["net", "stop", "ClawCat"], capture_output=True)

        # Remove the service
        result = subprocess.run(
            [python_path, service_script, "remove"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("Service removed successfully!")
            return True
        else:
            print(f"Removal failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--remove":
        remove_service()
    else:
        install_service()


if __name__ == "__main__":
    main()
