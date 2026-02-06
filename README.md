# Project Setup Guide 🚀

## 📌 Overview

This project uses **Python virtual environment (venv)** to manage dependencies and ensure a consistent development environment across machines.

---

## ✅ Prerequisites

Make sure you have installed:

* Python 3.8+
* pip (Python package manager)
* Git

Check versions:

```bash
python --version
pip --version
git --version
```

---

## ⚙️ Installation Steps

### 1️⃣ Clone the Repository

```bash
git clone <your-repository-url>
cd <project-folder>
```

---

### 2️⃣ Create Virtual Environment

```bash
python3 -m venv venv
```

---

### 3️⃣ Activate Virtual Environment

**Linux**

```bash
source venv/bin/activate.fish
```

**Windows**

```bash
venv\Scripts\activate
```

After activation you should see:

```
(venv)
```

---

### 4️⃣ Upgrade pip (Recommended)

```bash
pip install --upgrade pip
```

---

### 5️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages for the project.

---

## ▶️ Running the Project

Run your application:

```bash
python3 manage.py runserver
 or
daphne connectx.asgi:application

```

Then open:

```
http://127.0.0.1:8000/
```

---

## 🔄 Deactivate Virtual Environment

When finished working:

```bash
deactivate
```

---


## 👨‍💻 Recommended Workflow

✅ Activate venv
✅ Work on the project
✅ Install new packages when needed

If you install a new package, remember to update:

```bash
pip freeze > requirements.txt
```

---

## 🛠 Troubleshooting

### Packages not installing?

Try:

```bash
pip install --upgrade pip setuptools wheel
```

### Wrong Python version?

Use:

```bash
python3 -m venv venv
```

---

## ⭐ Best Practice

Always use a virtual environment for Python projects to avoid dependency conflicts and keep your system clean.

---

Happy Coding! 🎉
