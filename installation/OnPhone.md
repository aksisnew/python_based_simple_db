# Mobile Installation Guide (`OnPhone.md`)

> **⚠️ CAUTION & SECURITY NOTE**
> Use **Termux only** for running this application on your mobile device.
> Do **not** download Termux from unverified third-party sites.
> Always obtain Termux from a **verified, up-to-date source** (such as the official GitHub releases or F-Droid repository) to ensure security and package compatibility.And also make sure you are doing this on a secondary phone with no personal data, please be aware of security risks. I do these setups on my secondary development phone

---

## Step-by-Step Installation & Execution (No Proot-Distro)

Follow these sequential steps to set up your native Termux environment, configure a lightweight XFCE desktop interface for the GUI, and run the database application directly on your phone.

### Step 1: Install and Setup Termux
1. Download and install Termux from a **verified up-to-date source**.
2. Open Termux and update your package repositories:
   ```bash
   pkg update && pkg upgrade -y
   ~~~

  ## Install required 
~~~
  pkg install python python-tkinter -y
~~~

### Install a lightweight desktop env and x11 repo (for termux x11 app you need to download alongside the termux app for display output)



~~~
pkg install x11-repo -y

pkg install xfce4 termux-x11-nightly -y
~~~


## Get this repo on your phone, you need some tools for this pls install if you want or you can alternative way to actually get this repo on your termux environment and get this project running! this gets .zip of this repo.

~~~
curl -L -o project.zip https://github.com/aksisnew/python_based_simple_db/archive/refs/heads/main.zip
~~~

## then

~~~
unzip project.zip
~~~

## then 

~~~
cd python_based_simple_db-main
~~~

## cleanup 

~~~
rm ../project.zip
~~~

## cd into the folder and then 

~~~
python3 main.py
~~~
