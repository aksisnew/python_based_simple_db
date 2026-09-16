#!/bin/sh

# Detect environment
is_termux=0
if [ -n "$TERMUX_VERSION" ] || [ -d "/data/data/com.termux" ]; then
    is_termux=1
fi

# 1. Check if python3 exists on the system
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is not installed."
    echo ""
    if [ "$is_termux" -eq 1 ]; then
        echo "Detected System: Termux (Android)"
        echo "Please install python using:"
        echo "  pkg install python python-tkinter"
    elif [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            debian|ubuntu|linuxmint|pop|raspbian)
                echo "Detected System: Debian/Ubuntu-based ($NAME)"
                echo "Please install python3 using:"
                echo "  sudo apt update && sudo apt install python3 python3-tk"
                ;;
            *)
                echo "Detected System: Linux"
                echo "Please install python3 using your system's package manager."
                ;;
        esac
    else
        echo "Please install python3 using your package manager."
    fi
    echo ""
    echo "Please install (add the missing packages) and re run simpleGUIdb.sh"
    exit 1
fi

# 2. Check if tkinter is installed using system package managers
tkinter_missing=0
if [ "$is_termux" -eq 1 ]; then
    if ! dpkg -s python-tkinter >/dev/null 2>&1; then
        tkinter_missing=1
    fi
elif [ -f /etc/os-release ]; then
    . /etc/os-release
    case "$ID" in
        debian|ubuntu|linuxmint|pop|raspbian)
            if ! dpkg -s python3-tk >/dev/null 2>&1; then
                tkinter_missing=1
            fi
            ;;
        *)
            if ! dpkg -s python3-tk >/dev/null 2>&1 && ! rpm -q python3-tkinter >/dev/null 2>&1; then
                tkinter_missing=1
            fi
            ;;
    esac
fi

if [ "$tkinter_missing" -eq 1 ]; then
    echo "Error: Missing tkinter package."
    echo ""
    if [ "$is_termux" -eq 1 ]; then
        echo "Detected System: Termux (Android)"
        echo "Please install python-tkinter using:"
        echo "  pkg install python-tkinter"
    elif [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            debian|ubuntu|linuxmint|pop|raspbian)
                echo "Detected System: Debian/Ubuntu-based ($NAME)"
                echo "Please install python3-tk using:"
                echo "  sudo apt update && sudo apt install python3-tk"
                ;;
            *)
                echo "Detected System: Linux"
                echo "Please install python3-tk using your system's package manager."
                ;;
        esac
    else
        echo "Please install tkinter using your package manager."
    fi
    echo ""
    echo "Please install (add the missing packages) and re run simpleGUIdb.sh"
    exit 1
fi

# 3. Launch main.py with python3 interpreter
if [ -f "main.py" ]; then
    python3 main.py
else
    echo "Error: main.py not found in the project directory."
    exit 1
fi
