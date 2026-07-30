import os
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pandas as pd
from fpdf import FPDF
from io import BytesIO
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# ======== Konfigurasi Flask & Database ========
app = Flask(__name__, instance_relative_config=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'budget.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'bestisecret'

# Pastikan folder instance ada
os.makedirs(app.instance_path, exist_ok=True)

# Inisialisasi Database & Migrasi
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Inisialisasi Login Manager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = "info"
login_manager.init_app(app)

# ======== Models ========
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    # kolom type untuk menyimpan jenis kategori: Income / Expense / Tabungan
    type = db.Column(db.String(20), nullable=False, default='Expense')


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # Income, Expense, Tabungan
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship('Category', backref=db.backref('transactions', lazy=True))


# ======== Loader untuk Flask-Login ========
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ======== Routes: Auth ========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Ambil identifier dari input (username/email)
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

        if not identifier or not password:
            flash("⚠️ Semua field wajib diisi!", "warning")
            return redirect(url_for('login'))

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if user and user.check_password(password):
            login_user(user)
            flash("✅ Login berhasil, selamat datang!", "success")
            return redirect(url_for('index'))
        else:
            flash("⚠️ Email/Username atau password salah!", "danger")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    # Hapus semua pesan flash lama dari sesi
    session.pop('_flashes', None)

    # Logout user
    logout_user()

    # Flash pesan baru khusus logout
    flash("👋 Anda telah berhasil logout.", "info")

    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash("⚠️ Semua field wajib diisi!", "warning")
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash("⚠️ Username sudah digunakan!", "warning")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("⚠️ Email sudah digunakan!", "warning")
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("✅ Registrasi berhasil! Silakan login.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


# ======== Routes: Forgot & Reset Password ========
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user:
            flash("⚠️ Username/Email tidak ditemukan!", "danger")
            return redirect(url_for('forgot_password'))

        flash("🔑 Silakan atur password baru Anda.", "info")
        return redirect(url_for('reset_password', token=user.id))

    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.get(token)
    if not user:
        flash("⚠️ Token reset password tidak valid!", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not new_password or not confirm_password:
            flash("⚠️ Semua field wajib diisi!", "warning")
            return redirect(url_for('reset_password', token=token))

        if new_password != confirm_password:
            flash("⚠️ Password dan konfirmasi tidak cocok!", "danger")
            return redirect(url_for('reset_password', token=token))

        user.set_password(new_password)
        db.session.commit()
        flash("✅ Password berhasil diperbarui. Silakan login.", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)


# ======== Routes: Category Management (Data Master) ========
@app.route('/categories')
@login_required
def manage_categories():
    # ambil semua kategori lalu kelompokkan berdasarkan type
    categories = Category.query.order_by(Category.name).all()
    income_categories = [c for c in categories if c.type.lower() == 'income']
    expense_categories = [c for c in categories if c.type.lower() == 'expense']
    saving_categories = [c for c in categories if c.type.lower() in ('tabungan', 'saving', 'savings')]

    return render_template('categories.html',
                           income_categories=income_categories,
                           expense_categories=expense_categories,
                           saving_categories=saving_categories)


@app.route('/add_category', methods=['POST'])
@login_required
def add_category():
    name = request.form.get('name', '').strip()
    cat_type = request.form.get('type', '').strip()  # Expect "Income", "Expense" or "Tabungan"

    if not name:
        flash("⚠️ Nama kategori wajib diisi!", "danger")
        return redirect(url_for('manage_categories'))

    # cek duplikat nama
    existing = Category.query.filter_by(name=name).first()
    if existing:
        flash("⚠️ Kategori sudah ada!", "warning")
        return redirect(url_for('manage_categories'))

    # normalisasi tipe
    if cat_type.lower() not in ('income', 'expense', 'tabungan'):
        cat_type = 'Expense'

    cat = Category(name=name, type=cat_type)
    db.session.add(cat)
    db.session.commit()
    flash("✅ Kategori berhasil ditambahkan!", "success")
    return redirect(url_for('manage_categories'))


@app.route('/edit_category/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    cat = Category.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cat_type = request.form.get('type', '').strip()

        if not name:
            flash("⚠️ Nama kategori wajib diisi!", "warning")
            return redirect(url_for('edit_category', id=id))

        # cek duplikat (kecuali dirinya sendiri)
        other = Category.query.filter_by(name=name).first()
        if other and other.id != cat.id:
            flash("⚠️ Nama kategori sudah digunakan oleh kategori lain!", "warning")
            return redirect(url_for('edit_category', id=id))

        cat.name = name
        if cat_type.lower() in ('income', 'expense', 'tabungan'):
            cat.type = cat_type
        db.session.commit()
        flash("✅ Kategori berhasil diperbarui!", "success")
        return redirect(url_for('manage_categories'))

    return render_template('edit_category.html', category=cat)


@app.route('/delete_category/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    cat = Category.query.get_or_404(id)
    if cat.transactions:
        flash("⚠️ Kategori tidak bisa dihapus karena masih ada transaksi terkait!", "danger")
        return redirect(url_for('manage_categories'))
    db.session.delete(cat)
    db.session.commit()
    flash("✅ Kategori berhasil dihapus!", "success")
    return redirect(url_for('manage_categories'))


# ======== Routes: Edit Transaction ========
@app.route('/edit_transaction/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    categories = Category.query.all()

    if request.method == 'POST':
        type_ = request.form.get('type', '').strip()
        amount = request.form.get('amount', '').strip()
        date = request.form.get('date', '').strip()
        category_id = request.form.get('category_id', '').strip()
        custom_category = request.form.get('custom_category', '').strip()

        if not type_ or not amount or not date:
            flash("⚠️ Semua field wajib diisi!", "danger")
            return redirect(url_for('edit_transaction', id=id))

        if custom_category:
            existing = Category.query.filter_by(name=custom_category).first()
            if existing:
                category = existing
            else:
                category = Category(name=custom_category, type=type_)
                db.session.add(category)
                db.session.commit()
            transaction.category_id = category.id
        else:
            transaction.category_id = int(category_id)

        transaction.type = type_
        transaction.amount = float(amount)
        transaction.date = pd.to_datetime(date).date()

        db.session.commit()
        flash("✅ Transaksi berhasil diperbarui!", "success")
        return redirect(url_for('index'))

    return render_template('edit_transaction.html', transaction=transaction, categories=categories)


# ======== Routes: Index & Transaction (dengan overspending check) ========
@app.route('/')
@login_required
def index():
    # 🔐 Jika user belum login, arahkan ke halaman login
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    # Ambil data transaksi & kategori dari database
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    categories = Category.query.all()

    # Hitung total berdasarkan jenis transaksi
    total_income = sum(t.amount for t in transactions if t.type.lower() == 'income')
    total_expense = sum(t.amount for t in transactions if t.type.lower() == 'expense')
    total_tabungan = sum(t.amount for t in transactions if t.type.lower() == 'tabungan')
    balance = total_income - total_expense

    # 🔔 Logika notifikasi overspending
    if total_expense > total_income and total_income > 0:
        flash("⚠️ Peringatan: Pengeluaran Anda bulan ini melebihi pemasukan!", "danger")
    elif total_income > 0 and (balance / total_income) < 0.2:
        flash("💡 Tips: Saldo Anda tinggal kurang dari 20% dari pemasukan bulan ini.", "warning")

    # Render halaman utama
    return render_template(
        'index.html',
        transactions=transactions,
        categories=categories,
        total_income=total_income,
        total_expense=total_expense,
        total_tabungan=total_tabungan,
        balance=balance
    )


@app.route('/add_transaction', methods=['POST'])
@login_required 
def add_transaction():
    type_ = request.form.get('type', '').strip()
    amount = request.form.get('amount', '').strip()
    date = request.form.get('date', '').strip()
    category_id = request.form.get('category_id', '').strip()
    custom_category = request.form.get('custom_category', '').strip()

    if not type_ or not amount or not date:
        flash("⚠️ Semua field wajib diisi!", "danger")
        return redirect(url_for('index'))

    if custom_category:
        existing = Category.query.filter_by(name=custom_category).first()
        if existing:
            category = existing
        else:
            category = Category(name=custom_category, type=type_)
            db.session.add(category)
            db.session.commit()
        final_category_id = category.id
    else:
        final_category_id = int(category_id)

    transaction = Transaction(
        type=type_,
        amount=float(amount),
        date=pd.to_datetime(date).date(),
        category_id=final_category_id
    )
    db.session.add(transaction)
    db.session.commit()
    flash("✅ Transaksi berhasil ditambahkan!", "success")
    return redirect(url_for('index'))


@app.route('/delete_transaction/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    db.session.delete(transaction)
    db.session.commit()
    flash("✅ Transaksi berhasil dihapus!", "success")
    return redirect(url_for('index'))


# ======== Routes: Filter Transaksi (Pemasukan / Pengeluaran / Tabungan) ========
@app.route('/pemasukan')
@login_required
def pemasukan():
    transactions = Transaction.query.filter(Transaction.type.ilike('income')).order_by(Transaction.date.desc()).all()
    categories = Category.query.all()
    total_income = sum(t.amount for t in transactions if t.type.lower() == 'income')
    total_expense = sum(t.amount for t in transactions if t.type.lower() == 'expense')
    total_tabungan = sum(t.amount for t in transactions if t.type.lower() == 'tabungan')
    balance = total_income - total_expense
    return render_template('index.html', transactions=transactions, categories=categories,
                           total_income=total_income, total_expense=total_expense,
                           total_tabungan=total_tabungan, balance=balance)


@app.route('/pengeluaran')
@login_required
def pengeluaran():
    transactions = Transaction.query.filter(Transaction.type.ilike('expense')).order_by(Transaction.date.desc()).all()
    categories = Category.query.all()
    total_income = sum(t.amount for t in transactions if t.type.lower() == 'income')
    total_expense = sum(t.amount for t in transactions if t.type.lower() == 'expense')
    total_tabungan = sum(t.amount for t in transactions if t.type.lower() == 'tabungan')
    balance = total_income - total_expense
    return render_template('index.html', transactions=transactions, categories=categories,
                           total_income=total_income, total_expense=total_expense,
                           total_tabungan=total_tabungan, balance=balance)


@app.route('/tabungan')
@login_required
def tabungan():
    transactions = Transaction.query.filter(Transaction.type.ilike('tabungan')).order_by(Transaction.date.desc()).all()
    categories = Category.query.all()
    total_income = sum(t.amount for t in transactions if t.type.lower() == 'income')
    total_expense = sum(t.amount for t in transactions if t.type.lower() == 'expense')
    total_tabungan = sum(t.amount for t in transactions if t.type.lower() == 'tabungan')
    balance = total_income - total_expense
    return render_template('index.html', transactions=transactions, categories=categories,
                           total_income=total_income, total_expense=total_expense,
                           total_tabungan=total_tabungan, balance=balance)


# ======== Export ke Excel ========
@app.route('/export_excel')
@login_required
def export_excel():
    transactions = Transaction.query.all()
    data = [{
        'ID': t.id,
        'Jenis': t.type,
        'Nominal': t.amount,
        'Tanggal': t.date,
        'Kategori': t.category.name
    } for t in transactions]

    df = pd.DataFrame(data)
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")

    output.seek(0)
    return send_file(
        output,
        download_name="transactions.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ======== Export ke PDF ========
@app.route('/export_pdf')
@login_required
def export_pdf():
    transactions = Transaction.query.all()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Laporan Transaksi", ln=True, align='C')
    pdf.ln(10)

    # Header
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(10, 10, "ID", 1)
    pdf.cell(30, 10, "Jenis", 1)
    pdf.cell(30, 10, "Nominal", 1)
    pdf.cell(30, 10, "Tanggal", 1)
    pdf.cell(50, 10, "Kategori", 1)
    pdf.ln()

    # Data
    pdf.set_font("Arial", '', 12)
    for t in transactions:
        pdf.cell(10, 10, str(t.id), 1)
        pdf.cell(30, 10, t.type, 1)
        pdf.cell(30, 10, str(t.amount), 1)
        pdf.cell(30, 10, str(t.date), 1)
        pdf.cell(50, 10, t.category.name, 1)
        pdf.ln()

    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, download_name="transactions.pdf", as_attachment=True)


# ======== Jalankan Flask ========
if __name__ == '__main__':
    with app.app_context():
        # buat tabel jika belum ada
        db.create_all()

        # Jika kolom 'type' belum ada di tabel category, tambahkan (safe ALTER)
        try:
            with db.engine.connect() as conn:
                res = conn.execute("PRAGMA table_info(category)").fetchall()
                cols = [r[1] for r in res]
                if 'type' not in cols:
                    # tambahkan kolom type dengan default 'Expense' untuk kompatibilitas
                    conn.execute("ALTER TABLE category ADD COLUMN type VARCHAR(20) DEFAULT 'Expense'")
                    print("✅ Ditambahkan kolom 'type' ke tabel category (default 'Expense').")
        except Exception as e:
            # kalau gagal, tampilkan tapi lanjutkan (misalnya kalau DB baru atau locked)
            print("⚠️ Peringatan saat memastikan kolom 'type':", e)

        # Cek apakah user default sudah ada
        if not User.query.filter_by(username="admin").first():
            default_user = User(username="admin", email="admin@example.com")
            default_user.set_password("admin123")
            db.session.add(default_user)
            db.session.commit()
            print("✅ User default dibuat: admin / admin123")
        else:
            print("ℹ️ User default sudah ada.")

        print("✅ Database dan tabel dipastikan ada (User, Category, Transaction).")

    app.run(debug=True)
