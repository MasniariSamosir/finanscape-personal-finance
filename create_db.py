from app import db, app, Category

with app.app_context():
    db.create_all()
    # tambah kategori default supaya form dropdown bisa langsung dipakai
    categories = ['Food', 'Transport', 'Entertainment', 'Salary', 'Other']
    for cat_name in categories:
        category = Category(name=cat_name)
        db.session.add(category)
    db.session.commit()
    print("Database baru berhasil dibuat dengan tabel Category dan Transaction.")
