from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import datetime
import uuid

app = Flask(__name__, template_folder='templates')
app.secret_key = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

STORAGE_QUOTA_MB = 500

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(200))

class FileRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    filename = db.Column(db.String(300))
    original_filename = db.Column(db.String(300))
    file_size = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def home():
    files = FileRecord.query.filter_by(user_id=current_user.id).all()
    used_mb = sum(f.file_size for f in files) / (1024 * 1024)
    return render_template('index.html', files=files, used_mb=round(used_mb, 2))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))
        hashed = generate_password_hash(password)
        new_user = User(username=username, password=hashed)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No file selected!')
        return redirect(url_for('home'))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected!')
        return redirect(url_for('home'))
    filename = secure_filename(file.filename)
    unique_name = str(uuid.uuid4()) + '_' + filename
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
    size = os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
    record = FileRecord(user_id=current_user.id, filename=unique_name, original_filename=filename, file_size=size)
    db.session.add(record)
    db.session.commit()
    flash('File uploaded successfully!')
    return redirect(url_for('home'))

@app.route('/download/<int:file_id>')
@login_required
def download(file_id):
    record = FileRecord.query.get_or_404(file_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], record.filename, as_attachment=True, download_name=record.original_filename)

@app.route('/delete/<int:file_id>')
@login_required
def delete(file_id):
    record = FileRecord.query.get_or_404(file_id)
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], record.filename))
    except:
        pass
    db.session.delete(record)
    db.session.commit()
    flash('File deleted!')
    return redirect(url_for('home'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)