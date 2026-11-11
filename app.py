import os
import math
import io
from flask import Flask, render_template, request, redirect, url_for, session, Response
import sqlite3
import pandas as pd

app = Flask(__name__)
DB_PATH = 'intania60_2000.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = 'intania-secret-key-boss-only' 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_admin_credentials(username, password):
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        return user is not None
    except sqlite3.OperationalError:
        conn.close()
        return False

@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint and request.endpoint not in allowed_routes:
        if 'username' not in session:
            return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if check_admin_credentials(username, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = 'ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้องครับบอส!'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/export')
def export_data():
    conn = get_db_connection()
    query = '''
        SELECT 
            M.CuCode AS [รหัสสมาชิก], M.CLASS AS [รุ่น Intania], M.TITLE_T AS [คำนำหน้า], 
            M.NAME_T AS [ชื่อ], M.SNAME_T AS [นามสกุล], M.NINAME AS [ชื่อเล่น], 
            M.BIRTHDAY AS [วันเกิด], M.STATUS AS [สถานะภาพ],
            C.Email AS [อีเมล], C.Mobile AS [เบอร์มือถือ], C.Htel AS [โทรศัพท์บ้าน], C.Otel AS [โทรศัพท์ที่ทำงาน],
            A.Hno AS [บ้านเลขที่], A.Hsoi AS [ซอยที่อยู่], A.Hroad AS [ถนนที่อยู่], A.Hdistrict AS [เขต_อำเภอที่อยู่], A.Hprv AS [จังหวัดที่อยู่], A.Hzip AS [รหัสไปรษณีย์ที่อยู่],
            W.Company AS [บริษัท_องค์กร], W.POSITION AS [ตำแหน่งงาน], W.Business AS [ประเภทธุรกิจ]
        FROM Members M
        LEFT JOIN Contacts C ON M.CuCode = C.CuCode
        LEFT JOIN Addresses A ON M.CuCode = A.CuCode
        LEFT JOIN Workplaces W ON M.CuCode = W.CuCode
        WHERE M.NAME_T != '' AND M.NAME_T IS NOT NULL
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=intania_alumni_database.csv"})


# ➕ [ฟีเจอร์ใหม่] ระบบเพิ่มสมาชิกคนใหม่ (Add New Member Route)
@app.route('/add', methods=['GET', 'POST'])
def add_member():
    error = None
    if request.method == 'POST':
        cucode = request.form.get('CuCode').strip()
        
        if not cucode:
            error = 'จำเป็นต้องกรอกรหัสสมาชิกครับบอส!'
        else:
            conn = get_db_connection()
            # ตรวจสอบก่อนว่ารหัส CuCode นี้ถูกใช้ไปหรือยัง
            existing = conn.execute('SELECT CuCode FROM Members WHERE CuCode = ?', (cucode,)).fetchone()
            
            if existing:
                error = f'รหัสสมาชิก {cucode} นี้มีอยู่ในระบบแล้วครับบอส! ลองใช้รหัสอื่น'
                conn.close()
            else:
                try:
                    # ดึงข้อมูลจากฟอร์มหน้าเว็บ
                    title_t = request.form.get('TITLE_T')
                    name_t = request.form.get('NAME_T')
                    sname_t = request.form.get('SNAME_T')
                    niname = request.form.get('NINAME')
                    birthday = request.form.get('BIRTHDAY')
                    status = request.form.get('STATUS')
                    clss = request.form.get('CLASS')
                    
                    mobile = request.form.get('Mobile')
                    email = request.form.get('Email')
                    htel = request.form.get('Htel')
                    otel = request.form.get('Otel')
                    
                    hno = request.form.get('Hno')
                    hsoi = request.form.get('Hsoi')
                    hroad = request.form.get('Hroad')
                    hdistrict = request.form.get('Hdistrict')
                    hprv = request.form.get('Hprv')
                    hzip = request.form.get('Hzip')
                    
                    company = request.form.get('Company')
                    business = request.form.get('Business')
                    position = request.form.get('POSITION')
                    
                    # จัดการอัปโหลดรูปภาพ (ถ้ามี)
                    picture_name = ''
                    file = request.files.get('picture_file')
                    if file and allowed_file(file.filename):
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        filename = f"{cucode}.{ext}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        picture_name = filename

                    # ยิงคำสั่ง INSERT ลงทั้ง 4 ตารางพร้อมกัน
                    conn.execute('''
                        INSERT INTO Members (CuCode, CLASS, TITLE_T, NAME_T, SNAME_T, NINAME, BIRTHDAY, STATUS, Picture)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (cucode, clss, title_t, name_t, sname_t, niname, birthday, status, picture_name))
                    
                    conn.execute('''
                        INSERT INTO Contacts (CuCode, Mobile, Email, Htel, Otel)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (cucode, mobile, email, htel, otel))
                    
                    conn.execute('''
                        INSERT INTO Addresses (CuCode, Hno, Hsoi, Hroad, Hdistrict, Hprv, Hzip)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (cucode, hno, hsoi, hroad, hdistrict, hprv, hzip))
                    
                    conn.execute('''
                        INSERT INTO Workplaces (CuCode, Company, Business, POSITION)
                        VALUES (?, ?, ?, ?)
                    ''', (cucode, company, business, position))
                    
                    conn.commit()
                    conn.close()
                    
                    # บันทึกสำเร็จ ให้เด้งไปดูหน้าโปรไฟล์ของคนที่เพิ่งสร้างทันที
                    return redirect(url_for('profile', cucode=cucode, success=1))
                    
                except sqlite3.Error as e:
                    conn.rollback()
                    conn.close()
                    error = f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}"

    return render_template('add_member.html', error=error)


# --- หน้า Dashboard ---
@app.route('/')
def index():
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 50
    offset = (page - 1) * PER_PAGE

    conn = get_db_connection()
    stats = {}
    try:
        stats['total'] = conn.execute("SELECT COUNT(*) FROM Members WHERE NAME_T != '' AND NAME_T IS NOT NULL").fetchone()[0]
        stats['has_mobile'] = conn.execute("SELECT COUNT(*) FROM Contacts WHERE Mobile != '' AND Mobile IS NOT NULL").fetchone()[0]
        stats['total_classes'] = conn.execute("SELECT COUNT(DISTINCT CLASS) FROM Members WHERE CLASS != '' AND CLASS IS NOT NULL").fetchone()[0]
        stats['top_companies'] = conn.execute('''
            SELECT Company, COUNT(*) as count FROM Workplaces 
            WHERE Company != '' AND Company IS NOT NULL
            GROUP BY Company ORDER BY count DESC LIMIT 3
        ''').fetchall()
    except sqlite3.Error:
        stats = {'total': 0, 'has_mobile': 0, 'total_classes': 0, 'top_companies': []}

    if search_query:
        total_filtered = conn.execute('''
            SELECT COUNT(*) FROM Members 
            WHERE NAME_T LIKE ? OR SNAME_T LIKE ? OR CLASS LIKE ?
        ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchone()[0]

        members = conn.execute('''
            SELECT M.CuCode, M.CLASS, M.NAME_T, M.SNAME_T, C.Mobile, W.Company
            FROM Members M
            LEFT JOIN Contacts C ON M.CuCode = C.CuCode
            LEFT JOIN Workplaces W ON M.CuCode = W.CuCode
            WHERE M.NAME_T LIKE ? OR M.SNAME_T LIKE ? OR M.CLASS LIKE ?
            LIMIT ? OFFSET ?
        ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', PER_PAGE, offset)).fetchall()
    else:
        total_filtered = stats['total']
        members = conn.execute('''
            SELECT M.CuCode, M.CLASS, M.NAME_T, M.SNAME_T, C.Mobile, W.Company
            FROM Members M
            LEFT JOIN Contacts C ON M.CuCode = C.CuCode
            LEFT JOIN Workplaces W ON M.CuCode = W.CuCode
            WHERE M.NAME_T != '' 
            LIMIT ? OFFSET ?
        ''', (PER_PAGE, offset)).fetchall()
        
    conn.close()
    total_pages = math.ceil(total_filtered / PER_PAGE)
    
    return render_template('dashboard.html', 
                           members=members, search_query=search_query, stats=stats,
                           page=page, total_pages=total_pages, total_filtered=total_filtered)

# --- หน้า Profile ---
@app.route('/profile/<cucode>', methods=['GET', 'POST'])
def profile(cucode):
    if request.method == 'POST':
        conn = get_db_connection()
        try:
            title_t = request.form.get('TITLE_T')
            name_t = request.form.get('NAME_T')
            sname_t = request.form.get('SNAME_T')
            niname = request.form.get('NINAME')
            birthday = request.form.get('BIRTHDAY')
            status = request.form.get('STATUS')
            mobile = request.form.get('Mobile')
            email = request.form.get('Email')
            htel = request.form.get('Htel')
            otel = request.form.get('Otel')
            hno = request.form.get('Hno')
            hsoi = request.form.get('Hsoi')
            hroad = request.form.get('Hroad')
            hdistrict = request.form.get('Hdistrict')
            hprv = request.form.get('Hprv')
            company = request.form.get('Company')
            business = request.form.get('Business')
            position = request.form.get('POSITION')
            picture_name = request.form.get('current_picture', '')
            file = request.files.get('picture_file')
            
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{cucode}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                picture_name = filename

            conn.execute('UPDATE Members SET TITLE_T=?, NAME_T=?, SNAME_T=?, NINAME=?, BIRTHDAY=?, STATUS=?, Picture=? WHERE CuCode=?', (title_t, name_t, sname_t, niname, birthday, status, picture_name, cucode))
            conn.execute('UPDATE Contacts SET Mobile=?, Email=?, Htel=?, Otel=? WHERE CuCode=?', (mobile, email, htel, otel, cucode))
            conn.execute('UPDATE Addresses SET Hno=?, Hsoi=?, Hroad=?, Hdistrict=?, Hprv=? WHERE CuCode=?', (hno, hsoi, hroad, hdistrict, hprv, cucode))
            conn.execute('UPDATE Workplaces SET Company=?, Business=?, POSITION=? WHERE CuCode=?', (company, business, position, cucode))
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            return "ระบบมีปัญหาในการบันทึกข้อมูล", 500
        finally:
            conn.close()
        return redirect(url_for('profile', cucode=cucode, success=1))

    conn = get_db_connection()
    try:
        member = conn.execute('''
            SELECT M.CuCode, M.CLASS, M.TITLE_T, M.NAME_T, M.SNAME_T, M.NINAME, M.BIRTHDAY, M.STATUS, M.Picture,
                   C.Email, C.Mobile, C.Htel, C.Otel, A.Hno, A.Hsoi, A.Hroad, A.Hdistrict, A.Hprv, A.Hzip,
                   W.Company, W.POSITION, W.Business
            FROM Members M
            LEFT JOIN Contacts C ON M.CuCode = C.CuCode
            LEFT JOIN Addresses A ON M.CuCode = A.CuCode
            LEFT JOIN Workplaces W ON M.CuCode = W.CuCode
            WHERE M.CuCode = ?
        ''', (cucode,)).fetchone()
    finally:
        conn.close()
    if member is None: return "ไม่พบข้อมูลสมาชิก", 404
    show_success = request.args.get('success') == '1'
    return render_template('profile.html', member=member, show_success=show_success)

if __name__ == '__main__':
    app.run(debug=True, port=5000)