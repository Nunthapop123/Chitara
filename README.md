# Chitara

## Prerequisites
- Python 3.8+
- pip (Python package installer)

## Installation Guide

1. **Clone the repository** (if you haven't already downloaded the project folder)
   ```bash
   git clone https://github.com/Nunthapop123/Chitara.git
   cd Chitara
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   
   # On macOS/Linux:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   Ensure your virtual environment is activated, then install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the Database**
   Generate and apply the migrations to set up the database schema:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

## Running the Application & Demonstrating CRUD Operations

1. **Create an Admin Superuser**
   To interact with the database and demonstrate CRUD operations, you need an admin account:
   ```bash
   python manage.py createsuperuser
   ```
   Follow the prompts to set a username, email, and password.

2. **Run the Development Server**
   ```bash
   python manage.py runserver
   ```

3. **Log in to Django Admin**
   Open your browser and navigate to `http://127.0.0.1:8000/admin/`. Log in with the superuser credentials you just created.

From here, you can **Create, Read, Update, and Delete** any instance of the core domain entities:
- `Registered Users`
- `Libraries`
- `Generated Songs`