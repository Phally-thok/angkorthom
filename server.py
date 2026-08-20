import http.server
import socketserver
import urllib.parse
import json
import os
import sqlite3
import hashlib
from database import init_db, get_db_connection, generate_password_hash, check_password_hash, log_activity

PORT = 5000
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')

SESSIONS = {}

def parse_cookies(cookie_header):
    cookies = {}
    if cookie_header:
        for item in cookie_header.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                cookies[k] = v
    return cookies

def khmer_status(status_code):
    mapping = {
        'approved': 'បានអនុម័ត',
        'pending': 'រង់ចាំអនុម័ត',
        'completed': 'បានបញ្ចប់',
        'rejected': 'បានបដិសេធ',
        'active': 'កំពុងបម្រើការ',
        'transferred': 'បានផ្ទេរ',
        'retired': 'និវត្តន៍',
        'good': 'ល្អ',
        'repair_needed': 'ត្រូវជួសជុល',
        'broken': 'ខូច',
        'inbound': 'លិខិតចូល',
        'outbound': 'លិខិតចេញ',
        'scout': 'កាយរឹទ្ធិជាតិ',
        'volunteer': 'ស្ម័គ្រចិត្ត',
        'youth_club': 'ក្លឹបយុវជន',
        'primary': 'បឋមសិក្សា',
        'secondary': 'អនុវិទ្យាល័យ',
        'high': 'វិទ្យាល័យ',
        'PB_operational': 'ថវិកាប្រតិបត្តិការ (PB)',
        'school_development': 'ថវិកាអភិវឌ្ឍន៍សាលា'
    }
    return mapping.get(status_code, status_code)

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

class EduHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.startswith('/static/'):
            return os.path.join(os.path.dirname(__file__), path.lstrip('/'))
        return super().translate_path(path)

    def get_session(self):
        cookies = parse_cookies(self.headers.get('Cookie'))
        session_id = cookies.get('session_id')
        if session_id and session_id in SESSIONS:
            return SESSIONS[session_id], session_id
        return {}, None

    def save_session(self, session_data, session_id=None):
        if not session_id:
            session_id = hashlib.md5(os.urandom(16)).hexdigest()
        SESSIONS[session_id] = session_data
        return session_id

    def redirect(self, location, session_id=None):
        self.send_response(302)
        self.send_header('Location', location)
        if session_id:
            self.send_header('Set-Cookie', f'session_id={session_id}; Path=/; HttpOnly')
        self.end_headers()

    def do_GET(self):
        url_parts = urllib.parse.urlparse(self.path)
        path = url_parts.path
        query = urllib.parse.parse_qs(url_parts.query)

        session_data, session_id = self.get_session()

        if path.startswith('/static/'):
            return super().do_GET()

        if path == '/login':
            return self.serve_login()

        if not session_data.get('user_id'):
            return self.redirect('/login')

        if session_data.get('role') == 'other' and path not in ['/', '/dashboard', '/logout']:
            return self.redirect('/dashboard')

        if 'action' in query and query['action'][0] == 'delete':
            target = query.get('target', [''])[0]
            item_id = query.get('id', [''])[0]
            if item_id:
                conn = get_db_connection()
                target_map = {
                    'school': ('schools', 'សាលារៀន'),
                    'staff': ('staff', 'បុគ្គលិក'),
                    'student_stats': ('student_stats', 'ស្ថិតិសិស្ស'),
                    'exam_results': ('exam_results', 'លទ្ធផលប្រឡង'),
                    'athlete': ('sports_athletes', 'កីឡាករ'),
                    'youth': ('youth_clubs', 'ក្លឹបយុវជន'),
                    'document': ('documents', 'លិខិតស្នាម'),
                    'mission': ('mission_orders', 'បេសកកម្ម'),
                    'budget': ('budgets', 'ថវិកា'),
                    'asset': ('assets', 'ទ្រព្យសម្បត្តិ'),
                    'user': ('users', 'អ្នកប្រើប្រាស់')
                }
                if target in target_map:
                    table_name, module_kh = target_map[target]
                    conn.execute(f'DELETE FROM {table_name} WHERE id = ?', (item_id,))
                    log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'DELETE', module_kh, f"បានលុបទិន្នន័យ ID #{item_id} ពី {module_kh}")
                conn.commit()
                conn.close()
                return self.redirect(path)

        if path in ['/', '/dashboard']:
            return self.serve_dashboard(session_data)
        elif path == '/schools':
            return self.serve_schools(session_data)
        elif path == '/staff':
            return self.serve_staff(session_data)
        elif path == '/students':
            return self.serve_students(session_data)
        elif path == '/youth_sports':
            return self.serve_youth_sports(session_data)
        elif path == '/documents':
            return self.serve_documents(session_data)
        elif path == '/budget_assets':
            return self.serve_budget_assets(session_data)
        elif path == '/reports':
            return self.serve_reports(session_data)
        elif path == '/users':
            if session_data.get('role') != 'admin':
                return self.redirect('/dashboard')
            return self.serve_users(session_data)
        elif path == '/logs':
            if session_data.get('role') != 'admin':
                return self.redirect('/dashboard')
            return self.serve_logs(session_data)
        elif path == '/logout':
            if session_id in SESSIONS:
                del SESSIONS[session_id]
            return self.redirect('/login')
        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self):
        url_parts = urllib.parse.urlparse(self.path)
        path = url_parts.path

        content_length = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_length).decode('utf-8')
        form_data = urllib.parse.parse_qs(post_body)
        form = {k: v[0] for k, v in form_data.items()}

        session_data, session_id = self.get_session()

        if path == '/login':
            username = form.get('username')
            password = form.get('password')
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

            if user and check_password_hash(user['password_hash'], password):
                new_session = {
                    'user_id': user['id'],
                    'username': user['username'],
                    'user_name': user['full_name'],
                    'role': user['role'],
                    'school_id': user['school_id']
                }
                log_activity(conn, user['id'], user['username'], user['full_name'], 'LOGIN', 'ប្រព័ន្ធ', 'បានចូលប្រើប្រាស់ប្រព័ន្ធ')
                conn.close()
                sid = self.save_session(new_session)
                return self.redirect('/dashboard', sid)
            else:
                conn.close()
                return self.redirect('/login')

        if not session_data.get('user_id'):
            return self.redirect('/login')

        if session_data.get('role') == 'other':
            return self.redirect('/dashboard')

        conn = get_db_connection()

        if path == '/schools/add':
            school_id = form.get('school_id')
            if school_id:
                conn.execute('''
                    UPDATE schools SET code=?, name_kh=?, name_en=?, level=?, commune=?, village=?, principal_name=?, principal_phone=?, classrooms=?, buildings=?
                    WHERE id=?
                ''', (form.get('code'), form.get('name_kh'), form.get('name_en'), form.get('level'), form.get('commune'), form.get('village'), form.get('principal_name'), form.get('principal_phone'), form.get('classrooms', 0), form.get('buildings', 0), school_id))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'UPDATE', 'សាលារៀន', f"បានកែប្រែសាលារៀន: {form.get('name_kh')}")
            else:
                conn.execute('''
                    INSERT INTO schools (code, name_kh, name_en, level, commune, village, principal_name, principal_phone, classrooms, buildings)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (form.get('code'), form.get('name_kh'), form.get('name_en'), form.get('level'), form.get('commune'), form.get('village'), form.get('principal_name'), form.get('principal_phone'), form.get('classrooms', 0), form.get('buildings', 0)))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'CREATE', 'សាលារៀន', f"បានបង្កើតសាលារៀន: {form.get('name_kh')}")
            conn.commit()

        elif path == '/staff/add':
            staff_id = form.get('staff_id')
            if staff_id:
                conn.execute('''
                    UPDATE staff SET staff_id_num=?, name_kh=?, name_en=?, sex=?, school_id=?, framework=?, position=?, subject_specialty=?, current_grade=?, phone=?
                    WHERE id=?
                ''', (form.get('staff_id_num'), form.get('name_kh'), form.get('name_en'), form.get('sex'), form.get('school_id'), form.get('framework'), form.get('position'), form.get('subject_specialty'), form.get('current_grade'), form.get('phone'), staff_id))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'UPDATE', 'បុគ្គលិក', f"បានកែប្រែព័ត៌មានបុគ្គលិក: {form.get('name_kh')}")
            else:
                conn.execute('''
                    INSERT INTO staff (staff_id_num, name_kh, name_en, sex, school_id, framework, position, subject_specialty, current_grade, phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (form.get('staff_id_num'), form.get('name_kh'), form.get('name_en'), form.get('sex'), form.get('school_id'), form.get('framework'), form.get('position'), form.get('subject_specialty'), form.get('current_grade'), form.get('phone')))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'CREATE', 'បុគ្គលិក', f"បានបង្កើតព័ត៌មានបុគ្គលិក: {form.get('name_kh')}")
            conn.commit()

        elif path == '/students/add_stats':
            stat_id = form.get('stat_id')
            if stat_id:
                conn.execute('''
                    UPDATE student_stats SET school_id=?, academic_year=?, total_students=?, female_students=?, disabled_students=?, disabled_female=?, scholarship_students=?, scholarship_female=?, dropout_count=?, dropout_female=?, repetition_count=?
                    WHERE id=?
                ''', (form.get('school_id'), form.get('academic_year'), form.get('total_students', 0), form.get('female_students', 0), form.get('disabled_students', 0), form.get('disabled_female', 0), form.get('scholarship_students', 0), form.get('scholarship_female', 0), form.get('dropout_count', 0), form.get('dropout_female', 0), form.get('repetition_count', 0), stat_id))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'UPDATE', 'ស្ថិតិសិស្ស', f"បានកែប្រែស្ថិតិសិស្ស ឆ្នាំសិក្សា {form.get('academic_year')}")
            else:
                conn.execute('''
                    INSERT INTO student_stats (school_id, academic_year, total_students, female_students, disabled_students, disabled_female, scholarship_students, scholarship_female, dropout_count, dropout_female, repetition_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (form.get('school_id'), form.get('academic_year'), form.get('total_students', 0), form.get('female_students', 0), form.get('disabled_students', 0), form.get('disabled_female', 0), form.get('scholarship_students', 0), form.get('scholarship_female', 0), form.get('dropout_count', 0), form.get('dropout_female', 0), form.get('repetition_count', 0)))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'CREATE', 'ស្ថិតិសិស្ស', f"បានបញ្ចូលស្ថិតិសិស្ស ឆ្នាំសិក្សា {form.get('academic_year')}")
            conn.commit()

        elif path == '/documents/add':
            doc_id = form.get('doc_id')
            if doc_id:
                conn.execute('''
                    UPDATE documents SET doc_number=?, doc_type=?, title=?, source_destination=?, doc_date=?, category=?
                    WHERE id=?
                ''', (form.get('doc_number'), form.get('doc_type'), form.get('title'), form.get('source_destination'), form.get('doc_date'), form.get('category', 'លិខិតផ្លូវការ'), doc_id))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'UPDATE', 'លិខិតស្នាម', f"បានកែប្រែលិខិតផ្លូវការ: {form.get('doc_number')}")
            else:
                conn.execute('''
                    INSERT INTO documents (doc_number, doc_type, title, source_destination, doc_date, category, scanned_file, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'កត់ត្រារួច')
                ''', (form.get('doc_number'), form.get('doc_type'), form.get('title'), form.get('source_destination'), form.get('doc_date'), form.get('category', 'លិខិតផ្លូវការ'), form.get('scanned_file')))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'CREATE', 'លិខិតស្នាម', f"បានចុះលិខិតផ្លូវការ: {form.get('doc_number')}")
            conn.commit()

        elif path == '/documents/add_mission':
            mission_id = form.get('mission_id')
            if mission_id:
                conn.execute('''
                    UPDATE mission_orders SET mission_code=?, title=?, officer_names=?, destination_schools=?, start_date=?, end_date=?, purpose=?
                    WHERE id=?
                ''', (form.get('mission_code'), form.get('title'), form.get('officer_names'), form.get('destination_schools'), form.get('start_date'), form.get('end_date'), form.get('purpose'), mission_id))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'UPDATE', 'បេសកកម្ម', f"បានកែប្រែលិខិតបេសកកម្ម: {form.get('mission_code')}")
            else:
                conn.execute('''
                    INSERT INTO mission_orders (mission_code, title, officer_names, destination_schools, start_date, end_date, purpose, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'approved')
                ''', (form.get('mission_code'), form.get('title'), form.get('officer_names'), form.get('destination_schools'), form.get('start_date'), form.get('end_date'), form.get('purpose')))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'CREATE', 'បេសកកម្ម', f"បានបង្កើតលិខិតបេសកកម្ម: {form.get('mission_code')}")
            conn.commit()

        elif path == '/budget_assets/add_budget':
            conn.execute('''
                INSERT INTO budgets (school_id, academic_year, budget_type, allocated_amount, spent_amount, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (form.get('school_id'), form.get('academic_year'), form.get('budget_type'), form.get('allocated_amount', 0), form.get('spent_amount', 0), form.get('notes')))
            log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'CREATE', 'ថវិកា', f"បានបន្ថែមថវិកាប្រតិបត្តិការ ឆ្នាំ {form.get('academic_year')}")
            conn.commit()

        elif path == '/users/add':
            user_id = form.get('user_id')
            username = form.get('username')
            password = form.get('password')
            full_name = form.get('full_name')
            role = form.get('role')
            school_id = form.get('school_id') or None
            position = form.get('position')
            phone = form.get('phone')

            if user_id:
                if password and password.strip():
                    pwd_hash = generate_password_hash(password)
                    conn.execute('''
                        UPDATE users SET username=?, password_hash=?, full_name=?, role=?, school_id=?, position=?, phone=?
                        WHERE id=?
                    ''', (username, pwd_hash, full_name, role, school_id, position, phone, user_id))
                else:
                    conn.execute('''
                        UPDATE users SET username=?, full_name=?, role=?, school_id=?, position=?, phone=?
                        WHERE id=?
                    ''', (username, full_name, role, school_id, position, phone, user_id))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'UPDATE', 'អ្នកប្រើប្រាស់', f"បានកែប្រែគណនីអ្នកប្រើប្រាស់: {username}")
            else:
                pwd_hash = generate_password_hash(password if password else '123456')
                conn.execute('''
                    INSERT INTO users (username, password_hash, full_name, role, school_id, position, phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (username, pwd_hash, full_name, role, school_id, position, phone))
                log_activity(conn, session_data.get('user_id'), session_data.get('username'), session_data.get('user_name'), 'CREATE', 'អ្នកប្រើប្រាស់', f"បានបង្កើតគណនីអ្នកប្រើប្រាស់: {username}")
            conn.commit()

        conn.close()

        redirect_target = '/dashboard'
        if path.startswith('/schools'):
            redirect_target = '/schools'
        elif path.startswith('/staff'):
            redirect_target = '/staff'
        elif path.startswith('/students'):
            redirect_target = '/students'
        elif path.startswith('/documents'):
            redirect_target = '/documents'
        elif path.startswith('/budget_assets'):
            redirect_target = '/budget_assets'
        elif path.startswith('/users'):
            redirect_target = '/users'

        return self.redirect(redirect_target)

    def send_html(self, html_content):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

    def render_page(self, title, content_body, active_page, session_data):
        user_name = session_data.get('user_name', 'អ្នកប្រើប្រាស់')
        role_label = 'អ្នកគ្រប់គ្រង (Admin)' if session_data.get('role') == 'admin' else ('អ្នកប្រើប្រាស់ (User)' if session_data.get('role') == 'user' else 'ផ្សេងៗ (Other)')
        
        user_role = session_data.get('role')
        modules_nav = f"""
            <a href="/schools" class="nav-item {'active' if active_page=='schools' else ''}"><i class="fa-solid fa-school"></i> <span>១. គ្រប់គ្រងសាលារៀន</span></a>
            <a href="/staff" class="nav-item {'active' if active_page=='staff' else ''}"><i class="fa-solid fa-user-tie"></i> <span>២. គ្រប់គ្រងបុគ្គលិក & គ្រូ</span></a>
            <a href="/students" class="nav-item {'active' if active_page=='students' else ''}"><i class="fa-solid fa-user-graduate"></i> <span>៣. ស្ថិតិសិស្ស & លទ្ធផលប្រឡង</span></a>
            <a href="/youth_sports" class="nav-item {'active' if active_page=='youth_sports' else ''}"><i class="fa-solid fa-trophy"></i> <span>៤. យុវជន & កីឡា</span></a>
            <a href="/documents" class="nav-item {'active' if active_page=='documents' else ''}"><i class="fa-solid fa-file-contract"></i> <span>៥. លិខិតស្នាម & បេសកកម្ម</span></a>
            <a href="/budget_assets" class="nav-item {'active' if active_page=='budget_assets' else ''}"><i class="fa-solid fa-coins"></i> <span>៦. ថវិកា & ទ្រព្យសម្បត្តិ</span></a>
            <a href="/reports" class="nav-item {'active' if active_page=='reports' else ''}"><i class="fa-solid fa-file-export"></i> <span>៧. របាយការណ៍ & ទាញយក</span></a>
            """ if user_role in ['admin', 'user'] else ""

        admin_nav = f"""
            <a href="/users" class="nav-item {'active' if active_page=='users' else ''}"><i class="fa-solid fa-users-gear"></i> <span>៨. សិទ្ធិប្រើប្រាស់ (Users)</span></a>
            <a href="/logs" class="nav-item {'active' if active_page=='logs' else ''}"><i class="fa-solid fa-clock-rotate-left"></i> <span>៩. កំណត់ត្រាសកម្មភាព</span></a>
            """ if user_role == 'admin' else ""

        full_html = f"""<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <title>{title} - ការិយាល័យអប់រំ យុវជន និងកីឡា ស្រុកអង្គរធំ</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
<div class="app-container">
    <aside class="sidebar">
        <div class="sidebar-header">
            <div class="emblem-icon"><i class="fa-solid fa-graduation-cap"></i></div>
            <div class="header-titles">
                <h1>ការិយាល័យអប់រំ យុវជន និងកីឡា</h1>
                <p>ស្រុកអង្គរធំ • ខេត្តសៀមរាប</p>
            </div>
        </div>
        <nav class="sidebar-nav">
            <a href="/dashboard" class="nav-item {'active' if active_page=='dashboard' else ''}"><i class="fa-solid fa-chart-pie"></i> <span>ផ្ទាំងព័ត៌មាន (Dashboard)</span></a>
            {modules_nav}
            {admin_nav}
        </nav>
        <div class="sidebar-footer">
            <div class="user-profile-badge">
                <div class="user-avatar">{user_name[0]}</div>
                <div class="user-info">
                    <div class="user-name">{user_name}</div>
                    <div class="user-role-tag">{role_label}</div>
                </div>
                <a href="/logout" class="btn-logout" title="ចាកចេញ"><i class="fa-solid fa-right-from-bracket"></i></a>
            </div>
        </div>
    </aside>
    <main class="main-content">
        <header class="top-bar">
            <div class="page-title"><h2>{title}</h2></div>
            <div class="top-actions">
                <div class="search-box">
                    <i class="fa-solid fa-magnifying-glass"></i>
                    <input type="text" id="globalSearch" placeholder="ស្វែងរកទិន្នន័យ...">
                </div>
                <span class="badge badge-gold"><i class="fa-solid fa-location-dot"></i> ស្រុកអង្គរធំ ខេត្តសៀមរាប</span>
            </div>
        </header>
        <div class="content-body">
            {content_body}
        </div>
    </main>
</div>
<script src="/static/js/main.js"></script>
</body>
</html>"""
        self.send_html(full_html)

    def serve_login(self):
        html = """<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <title>ចូលប្រព័ន្ធ - ការិយាល័យអប់រំ យុវជន និងកីឡា ស្រុកអង្គរធំ</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="stylesheet" href="/static/css/style.css">
    <style>
        body { justify-content: center; align-items: center; }
        .login-card {
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-glow);
            border-radius: var(--radius-lg);
            width: 100%; max-width: 440px; padding: 40px 32px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.6); text-align: center;
        }
        .login-logo {
            width: 80px; height: 80px;
            background: linear-gradient(135deg, var(--accent-gold), var(--primary-light));
            border-radius: 20px; margin: 0 auto 20px;
            display: flex; align-items: center; justify-content: center;
            font-size: 40px; color: #fff; box-shadow: var(--shadow-glow);
        }
        .login-card h2 { font-size: 20px; color: #fff; margin-bottom: 6px; }
        .login-card p { font-size: 13px; color: var(--accent-gold); margin-bottom: 28px; }
        .demo-accounts {
            margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border-color);
            font-size: 12px; color: var(--text-muted); text-align: left;
        }
        .demo-accounts ul { list-style: none; margin-top: 6px; }
    </style>
</head>
<body>
<div class="login-card">
    <div class="login-logo"><i class="fa-solid fa-graduation-cap"></i></div>
    <h2>ប្រព័ន្ធគ្រប់គ្រងការិយាល័យអប់រំ យុវជន និងកីឡា</h2>
    <p>ស្រុកអង្គរធំ • ខេត្តសៀមរាប</p>
    <form action="/login" method="POST">
        <div class="form-group" style="text-align: left;">
            <label><i class="fa-solid fa-user"></i> ឈ្មោះគណនី (Username)</label>
            <input type="text" name="username" class="form-control" placeholder="បញ្ចូលឈ្មោះគណនី..." required>
        </div>
        <div class="form-group" style="text-align: left;">
            <label><i class="fa-solid fa-lock"></i> ពាក្យសម្ងាត់ (Password)</label>
            <input type="password" name="password" class="form-control" placeholder="បញ្ចូលពាក្យសម្ងាត់..." required>
        </div>
        <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; padding: 12px; margin-top: 10px;">
            <i class="fa-solid fa-right-to-bracket"></i> ចូលប្រើប្រាស់ប្រព័ន្ធ
        </button>
    </form>
</div>
</body>
</html>"""
        self.send_html(html)

    def serve_dashboard(self, session_data):
        conn = get_db_connection()
        total_schools = conn.execute('SELECT COUNT(*) FROM schools').fetchone()[0]
        total_staff = conn.execute('SELECT COUNT(*) FROM staff WHERE status = "active"').fetchone()[0]
        student_sum = conn.execute('SELECT SUM(total_students), SUM(female_students) FROM student_stats').fetchone()
        total_students = student_sum[0] or 0
        female_students = student_sum[1] or 0
        conn.close()

        content = f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-icon blue"><i class="fa-solid fa-school"></i></div>
                <div class="metric-info"><div class="label">សាលារៀនសរុប</div><div class="value">{total_schools}</div><div class="subtext">វិទ្យាល័យ 1 | អនុ 2 | បឋម 4</div></div>
            </div>
            <div class="metric-card">
                <div class="metric-icon gold"><i class="fa-solid fa-chalkboard-user"></i></div>
                <div class="metric-info"><div class="label">បុគ្គលិក & គ្រូបង្រៀន</div><div class="value">{total_staff}</div><div class="subtext">ក្របខ័ណ្ឌ ក, ខ, គ</div></div>
            </div>
            <div class="metric-card">
                <div class="metric-icon teal"><i class="fa-solid fa-user-graduate"></i></div>
                <div class="metric-info"><div class="label">សិស្សសរុបក្នុងស្រុក</div><div class="value">{total_students}</div><div class="subtext">សិស្សស្រី: {female_students}</div></div>
            </div>
            <div class="metric-card">
                <div class="metric-icon purple"><i class="fa-solid fa-award"></i></div>
                <div class="metric-info"><div class="label">អត្រាប្រឡងជាប់បាក់ឌុប</div><div class="value">84.4%</div><div class="subtext">ជាប់ 152 / 180 នាក់</div></div>
            </div>
        </div>"""
        self.render_page("ផ្ទាំងព័ត៌មាន និងស្ថិតិសង្ខេប (Dashboard)", content, 'dashboard', session_data)

    def serve_schools(self, session_data):
        conn = get_db_connection()
        schools = conn.execute('SELECT * FROM schools ORDER BY id ASC').fetchall()
        conn.close()

        rows = "".join([f"""<tr>
            <td><strong>{s['code']}</strong></td>
            <td><div style="font-weight: 600; color: #fff;">{s['name_kh']}</div><div style="font-size: 11px; color: var(--text-muted);">{s['name_en'] or ''}</div></td>
            <td><span class="badge badge-gold">{khmer_status(s['level'])}</span></td>
            <td>ឃុំ{s['commune']}, ភូមិ{s['village']}</td>
            <td>{s['principal_name']}</td>
            <td>{s['principal_phone']}</td>
            <td>{s['classrooms']} ថ្នាក់ / {s['buildings']} អគារ</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editSchoolModal({s['id']}, '{s['code']}', '{s['name_kh']}', '{s['name_en'] or ''}', '{s['level']}', '{s['commune']}', '{s['village']}', '{s['principal_name']}', '{s['principal_phone']}', {s['classrooms']}, {s['buildings']})">
                    <i class="fa-solid fa-pen"></i> កែប្រែ
                </button>
                <a href="/schools?action=delete&target=school&id={s['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបទិន្នន័យនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for s in schools])

        content = f"""
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="fa-solid fa-school"></i> បញ្ជីសាលារៀនក្នុងស្រុកអង្គរធំ</div>
                <button class="btn btn-primary" onclick="openModal('addSchoolModal')"><i class="fa-solid fa-plus"></i> បន្ថែមសាលារៀនថ្មី</button>
            </div>
            <div class="table-responsive">
                <table class="custom-table">
                    <thead><tr><th>កូដសាលា</th><th>ឈ្មោះសាលារៀន</th><th>កម្រិត</th><th>ទីតាំង</th><th>នាយកសាលា</th><th>លេខទូរស័ព្ទ</th><th>ថ្នាក់/អគារ</th><th>សកម្មភាព</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </div>

        <div class="modal-backdrop" id="addSchoolModal">
            <div class="modal-box">
                <div class="modal-header"><h3 id="schoolModalTitle"><i class="fa-solid fa-school"></i> បន្ថែមសាលារៀនថ្មី</h3><button class="modal-close" onclick="closeModal('addSchoolModal')">&times;</button></div>
                <form action="/schools/add" method="POST">
                    <input type="hidden" name="school_id" id="school_id">
                    <div class="modal-body">
                        <div class="form-row"><div class="form-group"><label>កូដសាលារៀន</label><input type="text" name="code" id="school_code" class="form-control" required></div><div class="form-group"><label>កម្រិត</label><select name="level" id="school_level" class="form-control"><option value="primary">បឋមសិក្សា</option><option value="secondary">អនុវិទ្យាល័យ</option><option value="high">វិទ្យាល័យ</option></select></div></div>
                        <div class="form-group"><label>ឈ្មោះសាលារៀន (ខ្មែរ)</label><input type="text" name="name_kh" id="school_name_kh" class="form-control" required></div>
                        <div class="form-group"><label>ឈ្មោះសាលារៀន (អង់គ្លេស)</label><input type="text" name="name_en" id="school_name_en" class="form-control"></div>
                        <div class="form-row"><div class="form-group"><label>ឃុំ</label><input type="text" name="commune" id="school_commune" class="form-control" required></div><div class="form-group"><label>ភូមិ</label><input type="text" name="village" id="school_village" class="form-control" required></div></div>
                        <div class="form-row"><div class="form-group"><label>ឈ្មោះនាយកសាលា</label><input type="text" name="principal_name" id="school_principal_name" class="form-control" required></div><div class="form-group"><label>លេខទូរស័ព្ទ</label><input type="text" name="principal_phone" id="school_principal_phone" class="form-control"></div></div>
                    </div>
                    <div class="modal-footer"><button type="button" class="btn btn-secondary" onclick="closeModal('addSchoolModal')">បោះបង់</button><button type="submit" class="btn btn-primary"><i class="fa-solid fa-floppy-disk"></i> រក្សាទុក</button></div>
                </form>
            </div>
        </div>

        <script>
        function editSchoolModal(id, code, name_kh, name_en, level, commune, village, principal_name, principal_phone, classrooms, buildings) {{
            document.getElementById('school_id').value = id;
            document.getElementById('school_code').value = code;
            document.getElementById('school_name_kh').value = name_kh;
            document.getElementById('school_name_en').value = name_en;
            document.getElementById('school_level').value = level;
            document.getElementById('school_commune').value = commune;
            document.getElementById('school_village').value = village;
            document.getElementById('school_principal_name').value = principal_name;
            document.getElementById('school_principal_phone').value = principal_phone;
            openModal('addSchoolModal');
        }}
        </script>"""
        self.render_page("១. គ្រប់គ្រងព័ត៌មានសាលារៀន", content, 'schools', session_data)

    def serve_staff(self, session_data):
        conn = get_db_connection()
        staff_list = conn.execute('SELECT st.*, sc.name_kh as school_name FROM staff st JOIN schools sc ON st.school_id = sc.id ORDER BY st.id DESC').fetchall()
        schools = conn.execute('SELECT id, name_kh FROM schools').fetchall()
        conn.close()

        rows = "".join([f"""<tr>
            <td><strong>{s['staff_id_num']}</strong></td>
            <td>{s['name_kh']}</td>
            <td>{s['school_name']}</td>
            <td><span class='badge badge-gold'>ក្របខ័ណ្ឌ {s['framework']}</span></td>
            <td>{s['position']}</td>
            <td>{s['subject_specialty']}</td>
            <td><span class='badge badge-success'>{khmer_status(s['status'])}</span></td>
            <td>{s['phone']}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editStaffModal({s['id']}, '{s['staff_id_num']}', '{s['name_kh']}', '{s['name_en']}', '{s['sex']}', {s['school_id']}, '{s['framework']}', '{s['position']}', '{s['subject_specialty']}', '{s['current_grade'] or ''}', '{s['phone'] or ''}')">
                    <i class="fa-solid fa-pen"></i> កែប្រែ
                </button>
                <a href="/staff?action=delete&target=staff&id={s['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបទិន្នន័យគ្រូបង្រៀននេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for s in staff_list])

        school_options = "".join([f"<option value='{sch['id']}'>{sch['name_kh']}</option>" for sch in schools])

        content = f"""
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="fa-solid fa-id-card"></i> ប្រវត្តិរូបគ្រូបង្រៀន និងបុគ្គលិកអប់រំ</div>
                <button class="btn btn-primary" onclick="openModal('addStaffModal')"><i class="fa-solid fa-user-plus"></i> បន្ថែមគ្រូថ្មី</button>
            </div>
            <div class="table-responsive">
                <table class="custom-table">
                    <thead><tr><th>អត្តលេខ</th><th>ឈ្មោះ</th><th>សាលារៀន</th><th>ក្របខ័ណ្ឌ</th><th>តួនាទី</th><th>ជំនាញ</th><th>ស្ថានភាព</th><th>លេខទូរស័ព្ទ</th><th>សកម្មភាព</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </div>

        <div class="modal-backdrop" id="addStaffModal">
            <div class="modal-box">
                <div class="modal-header"><h3 id="staffModalTitle"><i class="fa-solid fa-user-plus"></i> បន្ថែមប្រវត្តិរូបគ្រូថ្មី</h3><button class="modal-close" onclick="closeModal('addStaffModal')">&times;</button></div>
                <form action="/staff/add" method="POST">
                    <input type="hidden" name="staff_id" id="staff_id">
                    <div class="modal-body">
                        <div class="form-row"><div class="form-group"><label>អត្តលេខ</label><input type="text" name="staff_id_num" id="staff_id_num" class="form-control" required></div><div class="form-group"><label>ភេទ</label><select name="sex" id="staff_sex" class="form-control"><option value="M">ប្រុស</option><option value="F">ស្រី</option></select></div></div>
                        <div class="form-row"><div class="form-group"><label>ឈ្មោះខ្មែរ</label><input type="text" name="name_kh" id="staff_name_kh" class="form-control" required></div><div class="form-group"><label>ឈ្មោះអង់គ្លេស</label><input type="text" name="name_en" id="staff_name_en" class="form-control" required></div></div>
                        <div class="form-row"><div class="form-group"><label>សាលារៀន</label><select name="school_id" id="staff_school_id" class="form-control">{school_options}</select></div><div class="form-group"><label>ក្របខ័ណ្ឌ</label><select name="framework" id="staff_framework" class="form-control"><option value="A">ក</option><option value="B">ខ</option><option value="C">គ</option></select></div></div>
                        <div class="form-row"><div class="form-group"><label>តួនាទី</label><input type="text" name="position" id="staff_position" class="form-control" required></div><div class="form-group"><label>ជំនាញ</label><input type="text" name="subject_specialty" id="staff_subject_specialty" class="form-control" required></div></div>
                        <div class="form-group"><label>លេខទូរស័ព្ទ</label><input type="text" name="phone" id="staff_phone" class="form-control"></div>
                    </div>
                    <div class="modal-footer"><button type="button" class="btn btn-secondary" onclick="closeModal('addStaffModal')">បោះបង់</button><button type="submit" class="btn btn-primary"><i class="fa-solid fa-floppy-disk"></i> រក្សាទុក</button></div>
                </form>
            </div>
        </div>

        <script>
        function editStaffModal(id, id_num, name_kh, name_en, sex, school_id, framework, pos, specialty, grade, phone) {{
            document.getElementById('staff_id').value = id;
            document.getElementById('staff_id_num').value = id_num;
            document.getElementById('staff_name_kh').value = name_kh;
            document.getElementById('staff_name_en').value = name_en;
            document.getElementById('staff_sex').value = sex;
            document.getElementById('staff_school_id').value = school_id;
            document.getElementById('staff_framework').value = framework;
            document.getElementById('staff_position').value = pos;
            document.getElementById('staff_subject_specialty').value = specialty;
            document.getElementById('staff_phone').value = phone;
            document.getElementById('staffModalTitle').innerHTML = '<i class="fa-solid fa-pen-to-square"></i> កែប្រែប្រវត្តិរូបគ្រូបង្រៀន';
            openModal('addStaffModal');
        }}
        </script>"""
        self.render_page("២. គ្រប់គ្រងបុគ្គលិកអប់រំ និងគ្រូបង្រៀន", content, 'staff', session_data)

    def serve_students(self, session_data):
        conn = get_db_connection()
        stats_list = conn.execute('SELECT st.*, sc.name_kh as school_name FROM student_stats st JOIN schools sc ON st.school_id = sc.id ORDER BY st.id DESC').fetchall()
        exam_list = conn.execute('SELECT ex.*, sc.name_kh as school_name FROM exam_results ex JOIN schools sc ON ex.school_id = sc.id ORDER BY ex.id DESC').fetchall()
        schools = conn.execute('SELECT id, name_kh FROM schools ORDER BY name_kh ASC').fetchall()
        conn.close()

        school_options = "".join([f'<option value="{s["id"]}">{s["name_kh"]}</option>' for s in schools])

        st_rows = "".join([f"""<tr>
            <td><strong>{st['school_name']}</strong></td>
            <td>{st['academic_year']}</td>
            <td><span class='badge badge-primary'>{st['total_students']} នាក់</span></td>
            <td>{st['female_students']} នាក់</td>
            <td>{st['disabled_students']} នាក់</td>
            <td>{st.get('disabled_female', 0)} នាក់</td>
            <td><span class='badge badge-gold'>{st['scholarship_students']} នាក់</span></td>
            <td><span class='badge badge-gold'>{st.get('scholarship_female', 0)} នាក់</span></td>
            <td><span class='badge badge-danger'>{st['dropout_count']} នាក់</span></td>
            <td><span class='badge badge-danger'>{st.get('dropout_female', 0)} នាក់</span></td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editStudentStats({st['id']}, {st['school_id']}, '{st['academic_year']}', {st['total_students']}, {st['female_students']}, {st['disabled_students']}, {st.get('disabled_female', 0)}, {st['scholarship_students']}, {st.get('scholarship_female', 0)}, {st['dropout_count']}, {st.get('dropout_female', 0)}, {st['repetition_count']})">
                    <i class="fa-solid fa-pen"></i> កែប្រែ
                </button>
                <a href="/students?action=delete&target=student_stats&id={st['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបទិន្នន័យនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for st in stats_list])

        ex_rows = "".join([f"""<tr>
            <td><strong>{ex['school_name']}</strong></td>
            <td>{ex['academic_year']}</td>
            <td><span class='badge badge-gold'>{khmer_status(ex['exam_type'])}</span></td>
            <td>{ex['total_candidates']} នាក់</td>
            <td><strong style='color: var(--accent-teal);'>{ex['total_passed']} នាក់</strong></td>
            <td>A:{ex['grade_a']} | B:{ex['grade_b']} | C:{ex['grade_c']}</td>
            <td>
                <a href="/students?action=delete&target=exam_results&id={ex['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបលទ្ធផលប្រឡងនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for ex in exam_list])

        content = f"""
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="fa-solid fa-users"></i> ស្ថិតិសិស្សតាមសាលានីមួយៗ</div>
                <div style="display: flex; gap: 8px;">
                    <a href="/schools" class="btn btn-secondary btn-sm"><i class="fa-solid fa-school"></i> បន្ថែមសាលា</a>
                    <button class="btn btn-primary btn-sm" onclick="openModal('addStudentStatsModal')"><i class="fa-solid fa-plus"></i> បញ្ជូន/កែប្រែ ស្ថិតិសិស្ស</button>
                </div>
            </div>
            <div class="table-responsive">
                <table class="custom-table">
                    <thead>
                        <tr>
                            <th rowspan="2">សាលារៀន</th>
                            <th rowspan="2">ឆ្នាំសិក្សា</th>
                            <th rowspan="2">សិស្សសរុប</th>
                            <th rowspan="2">សិស្សស្រី</th>
                            <th colspan="2" style="text-align: center;">ពិការភាព</th>
                            <th colspan="2" style="text-align: center;">អាហារូបករណ៍</th>
                            <th colspan="2" style="text-align: center;">បោះបង់</th>
                            <th rowspan="2">សកម្មភាព</th>
                        </tr>
                        <tr>
                            <th>សរុប</th>
                            <th>ស្រី</th>
                            <th>សរុប</th>
                            <th>ស្រី</th>
                            <th>សរុប</th>
                            <th>ស្រី</th>
                        </tr>
                    </thead>
                    <tbody>{st_rows}</tbody>
                </table>
            </div>
        </div>
        <div class="panel">
            <div class="panel-header"><div class="panel-title"><i class="fa-solid fa-award"></i> លទ្ធផលប្រឡងឌីប្លូម និងបាក់ឌុប</div></div>
            <div class="table-responsive"><table class="custom-table"><thead><tr><th>សាលារៀន</th><th>ឆ្នាំសិក្សា</th><th>ប្រភេទប្រឡង</th><th>បេក្ខជន</th><th>ប្រឡងជាប់</th><th>និទ្ទេស</th><th>សកម្មភាព</th></tr></thead><tbody>{ex_rows}</tbody></table></div>
        </div>

        <div class="modal-backdrop" id="addStudentStatsModal">
            <div class="modal-box">
                <div class="modal-header">
                    <h3 id="studentStatsModalTitle"><i class="fa-solid fa-users"></i> បញ្ជូន/ធ្វើបច្ចុប្បន្នភាព ស្ថិតិសិស្ស</h3>
                    <button class="modal-close" onclick="closeModal('addStudentStatsModal')">&times;</button>
                </div>
                <form action="/students/add_stats" method="POST">
                    <input type="hidden" name="stat_id" id="stat_id">
                    <div class="modal-body">
                        <div class="form-row">
                            <div class="form-group">
                                <label>សាលារៀន</label>
                                <select name="school_id" id="stat_school_id" class="form-control" required>
                                    {school_options}
                                </select>
                            </div>
                            <div class="form-group">
                                <label>ឆ្នាំសិក្សា</label>
                                <input type="text" name="academic_year" id="stat_academic_year" class="form-control" value="2025-2026" required>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>ចំនួនសិស្សសរុប</label>
                                <input type="number" name="total_students" id="stat_total_students" class="form-control" required>
                            </div>
                            <div class="form-group">
                                <label>ចំនួនសិស្សស្រី</label>
                                <input type="number" name="female_students" id="stat_female_students" class="form-control" required>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>សិស្សពិការភាព (សរុប)</label>
                                <input type="number" name="disabled_students" id="stat_disabled_students" class="form-control" value="0">
                            </div>
                            <div class="form-group">
                                <label>សិស្សពិការភាព (ស្រី)</label>
                                <input type="number" name="disabled_female" id="stat_disabled_female" class="form-control" value="0">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>សិស្សអាហារូបករណ៍ (សរុប)</label>
                                <input type="number" name="scholarship_students" id="stat_scholarship_students" class="form-control" value="0">
                            </div>
                            <div class="form-group">
                                <label>សិស្សអាហារូបករណ៍ (ស្រី)</label>
                                <input type="number" name="scholarship_female" id="stat_scholarship_female" class="form-control" value="0">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>ចំនួនសិស្សបោះបង់ (សរុប)</label>
                                <input type="number" name="dropout_count" id="stat_dropout_count" class="form-control" value="0">
                            </div>
                            <div class="form-group">
                                <label>ចំនួនសិស្សបោះបង់ (ស្រី)</label>
                                <input type="number" name="dropout_female" id="stat_dropout_female" class="form-control" value="0">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>ចំនួនសិស្សត្រួតថ្នាក់</label>
                                <input type="number" name="repetition_count" id="stat_repetition_count" class="form-control" value="0">
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal('addStudentStatsModal')">បោះបង់</button>
                        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-floppy-disk"></i> រក្សាទុក</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
        function editStudentStats(id, school_id, academic_year, total, female, disabled_tot, disabled_fem, scholarship_tot, scholarship_fem, dropout_tot, dropout_fem, repetition) {{
            document.getElementById('stat_id').value = id;
            document.getElementById('stat_school_id').value = school_id;
            document.getElementById('stat_academic_year').value = academic_year;
            document.getElementById('stat_total_students').value = total;
            document.getElementById('stat_female_students').value = female;
            document.getElementById('stat_disabled_students').value = disabled_tot;
            document.getElementById('stat_disabled_female').value = disabled_fem;
            document.getElementById('stat_scholarship_students').value = scholarship_tot;
            document.getElementById('stat_scholarship_female').value = scholarship_fem;
            document.getElementById('stat_dropout_count').value = dropout_tot;
            document.getElementById('stat_dropout_female').value = dropout_fem;
            document.getElementById('stat_repetition_count').value = repetition;
            openModal('addStudentStatsModal');
        }}
        </script>"""
        self.render_page("៣. គ្រប់គ្រងស្ថិតិសិស្ស និងលទ្ធផលសិក្សា", content, 'students', session_data)

    def serve_youth_sports(self, session_data):
        conn = get_db_connection()
        athletes = conn.execute('SELECT sa.*, sc.name_kh as school_name FROM sports_athletes sa JOIN schools sc ON sa.school_id = sc.id ORDER BY sa.id DESC').fetchall()
        youth = conn.execute('SELECT * FROM youth_clubs ORDER BY id DESC').fetchall()
        conn.close()

        ath_rows = "".join([f"""<tr>
            <td><strong>{a['athlete_name']}</strong></td>
            <td>{a['school_name']}</td>
            <td><span class='badge badge-primary'>{a['sport_type']}</span></td>
            <td><span class='badge badge-gold'><i class='fa-solid fa-medal'></i> {a['achievement']}</span></td>
            <td>
                <a href="/youth_sports?action=delete&target=athlete&id={a['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបឈ្មោះកីឡាករនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for a in athletes])

        youth_rows = "".join([f"""<tr>
            <td><strong>{y['title']}</strong></td>
            <td><span class='badge badge-gold'>{khmer_status(y['club_type'])}</span></td>
            <td>{y['location']}</td>
            <td>{y['leader_name']}</td>
            <td>{y['total_members']} នាក់</td>
            <td>
                <a href="/youth_sports?action=delete&target=youth&id={y['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបសកម្មភាពនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for y in youth])

        content = f"""
        <div class="panel">
            <div class="panel-header"><div class="panel-title"><i class="fa-solid fa-person-running"></i> កីឡាករជ័យលាភីស្រុកអង្គរធំ</div></div>
            <div class="table-responsive"><table class="custom-table"><thead><tr><th>ឈ្មោះកីឡាករ</th><th>សាលារៀន</th><th>ប្រភេទកីឡា</th><th>ជ័យលាភី</th><th>សកម្មភាព</th></tr></thead><tbody>{ath_rows}</tbody></table></div>
        </div>
        <div class="panel">
            <div class="panel-header"><div class="panel-title"><i class="fa-solid fa-campground"></i> ក្លឹបយុវជន & កាយរឹទ្ធិជាតិ</div></div>
            <div class="table-responsive"><table class="custom-table"><thead><tr><th>ឈ្មោះកម្មវិធី</th><th>ប្រភេទ</th><th>ទីតាំង</th><th>ប្រធាន</th><th>សមាជិក</th><th>សកម្មភាព</th></tr></thead><tbody>{youth_rows}</tbody></table></div>
        </div>"""
        self.render_page("៤. គ្រប់គ្រងសកម្មភាពយុវជន និងកីឡា", content, 'youth_sports', session_data)

    def serve_documents(self, session_data):
        conn = get_db_connection()
        docs = conn.execute('SELECT * FROM documents ORDER BY id DESC').fetchall()
        missions = conn.execute('SELECT * FROM mission_orders ORDER BY id DESC').fetchall()
        conn.close()

        doc_rows = "".join([f"""<tr>
            <td><strong>{d['doc_number']}</strong></td>
            <td><span class='badge badge-gold'>{khmer_status(d['doc_type'])}</span></td>
            <td>{d['title']}</td>
            <td>{d['source_destination']}</td>
            <td>{d['doc_date']}</td>
            <td><span class='badge badge-success'>{khmer_status(d['status'])}</span></td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editDocModal({d['id']}, '{d['doc_number']}', '{d['doc_type']}', '{d['title']}', '{d['source_destination']}', '{d['doc_date']}', '{d['category']}')">
                    <i class="fa-solid fa-pen"></i> កែប្រែ
                </button>
                <a href="/documents?action=delete&target=document&id={d['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបលិខិតនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for d in docs])

        mis_rows = "".join([f"""<tr>
            <td><strong>{m['mission_code']}</strong></td>
            <td>{m['title']}</td>
            <td>{m['officer_names']}</td>
            <td>{m['destination_schools']}</td>
            <td>{m['start_date']} ដល់ {m['end_date']}</td>
            <td><span class='badge badge-success'><i class='fa-solid fa-circle-check'></i> {khmer_status(m['status'])}</span></td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editMissionModal({m['id']}, '{m['mission_code']}', '{m['title']}', '{m['officer_names']}', '{m['destination_schools']}', '{m['start_date']}', '{m['end_date']}', '{m['purpose']}')">
                    <i class="fa-solid fa-pen"></i> កែប្រែ
                </button>
                <a href="/documents?action=delete&target=mission&id={m['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបលិខិតបង្គាប់ការនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for m in missions])

        content = f"""
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="fa-solid fa-book-bookmark"></i> សៀវភៅលិខិតចូល-ចេញ (Inbound/Outbound Letters)</div>
                <button class="btn btn-secondary btn-sm" onclick="openModal('addDocumentModal')"><i class="fa-solid fa-plus"></i> ចុះបញ្ជីលិខិតផ្លូវការ</button>
            </div>
            <div class="table-responsive"><table class="custom-table"><thead><tr><th>លេខលិខិត</th><th>ប្រភេទ</th><th>ចំណងជើង</th><th>ប្រភព/គោលដៅ</th><th>កាលបរិច្ឆេទ</th><th>ស្ថានភាព</th><th>សកម្មភាព</th></tr></thead><tbody>{doc_rows}</tbody></table></div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="fa-solid fa-plane-departure"></i> គ្រប់គ្រងលិខិតបង្គាប់ការ / ចុះបេសកកម្មមន្ត្រី</div>
                <button class="btn btn-primary" onclick="openModal('addMissionModal')"><i class="fa-solid fa-file-circle-check"></i> ចេញលិខិតបង្គាប់ការថ្មី</button>
            </div>
            <div class="table-responsive">
                <table class="custom-table">
                    <thead><tr><th>កូដបេសកកម្ម</th><th>កម្មវត្ថុ / បេសកកម្ម</th><th>មន្ត្រីចុះបេសកកម្ម</th><th>សាលារៀនគោលដៅ</th><th>កាលបរិច្ឆេទ</th><th>ស្ថានភាព</th><th>សកម្មភាព</th></tr></thead>
                    <tbody>{mis_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- Modal Add/Edit Document -->
        <div class="modal-backdrop" id="addDocumentModal">
            <div class="modal-box">
                <div class="modal-header"><h3 id="docModalTitle"><i class="fa-solid fa-file-circle-plus"></i> ចុះបញ្ជីលិខិតផ្លូវការ</h3><button class="modal-close" onclick="closeModal('addDocumentModal')">&times;</button></div>
                <form action="/documents/add" method="POST">
                    <input type="hidden" name="doc_id" id="doc_id">
                    <div class="modal-body">
                        <div class="form-row"><div class="form-group"><label>លេខលិខិត</label><input type="text" name="doc_number" id="doc_number" class="form-control" required></div><div class="form-group"><label>ប្រភេទ</label><select name="doc_type" id="doc_type" class="form-control"><option value="inbound">លិខិតចូល</option><option value="outbound">លិខិតចេញ</option></select></div></div>
                        <div class="form-group"><label>ចំណងជើងលិខិត</label><input type="text" name="title" id="doc_title" class="form-control" required></div>
                        <div class="form-row"><div class="form-group"><label>ប្រភព/គោលដៅ</label><input type="text" name="source_destination" id="doc_source_dest" class="form-control" required></div><div class="form-group"><label>កាលបរិច្ឆេទ</label><input type="date" name="doc_date" id="doc_date" class="form-control" required></div></div>
                    </div>
                    <div class="modal-footer"><button type="button" class="btn btn-secondary" onclick="closeModal('addDocumentModal')">បោះបង់</button><button type="submit" class="btn btn-primary"><i class="fa-solid fa-floppy-disk"></i> រក្សាទុក</button></div>
                </form>
            </div>
        </div>

        <!-- Modal Add/Edit Mission Order -->
        <div class="modal-backdrop" id="addMissionModal">
            <div class="modal-box">
                <div class="modal-header"><h3 id="missionModalTitle"><i class="fa-solid fa-file-circle-check"></i> ចេញលិខិតបង្គាប់ការ / បេសកកម្មថ្មី</h3><button class="modal-close" onclick="closeModal('addMissionModal')">&times;</button></div>
                <form action="/documents/add_mission" method="POST">
                    <input type="hidden" name="mission_id" id="mission_id">
                    <div class="modal-body">
                        <div class="form-row">
                            <div class="form-group"><label>កូដបេសកកម្ម</label><input type="text" name="mission_code" id="mission_code" class="form-control" placeholder="ឧ. MO-2026-003" required></div>
                            <div class="form-group"><label>កម្មវត្ថុបេសកកម្ម</label><input type="text" name="title" id="mission_title" class="form-control" placeholder="ឧ. ការពិនិត្យការបង្រៀន..." required></div>
                        </div>
                        <div class="form-group"><label>ឈ្មោះមន្ត្រីចុះបេសកកម្ម</label><input type="text" name="officer_names" id="mission_officers" class="form-control" placeholder="ឧ. លោក រ៉ាត់ សំអឿន, លោក អ៊ឹម សុធា" required></div>
                        <div class="form-group"><label>សាលារៀនគោលដៅ</label><input type="text" name="destination_schools" id="mission_dests" class="form-control" placeholder="ឧ. អនុវិទ្យាល័យ ពាក់ស្នែង" required></div>
                        <div class="form-row">
                            <div class="form-group"><label>ថ្ងៃចាប់ផ្តើម</label><input type="date" name="start_date" id="mission_start" class="form-control" required></div>
                            <div class="form-group"><label>ថ្ងៃបញ្ចប់</label><input type="date" name="end_date" id="mission_end" class="form-control" required></div>
                        </div>
                        <div class="form-group"><label>ភារកិច្ច/គោលបំណង</label><textarea name="purpose" id="mission_purpose" class="form-control" rows="2" placeholder="រៀបរាប់ពីភារកិច្ច..."></textarea></div>
                    </div>
                    <div class="modal-footer"><button type="button" class="btn btn-secondary" onclick="closeModal('addMissionModal')">បោះបង់</button><button type="submit" class="btn btn-primary"><i class="fa-solid fa-floppy-disk"></i> រក្សាទុក</button></div>
                </form>
            </div>
        </div>

        <script>
        function editMissionModal(id, code, title, officers, dests, start, end, purpose) {{
            document.getElementById('mission_id').value = id;
            document.getElementById('mission_code').value = code;
            document.getElementById('mission_title').value = title;
            document.getElementById('mission_officers').value = officers;
            document.getElementById('mission_dests').value = dests;
            document.getElementById('mission_start').value = start;
            document.getElementById('mission_end').value = end;
            document.getElementById('mission_purpose').value = purpose;
            document.getElementById('missionModalTitle').innerHTML = '<i class="fa-solid fa-pen-to-square"></i> កែប្រែលិខិតបង្គាប់ការ / បេសកកម្ម';
            openModal('addMissionModal');
        }}

        function editDocModal(id, doc_num, doc_type, title, source_dest, doc_date, category) {{
            document.getElementById('doc_id').value = id;
            document.getElementById('doc_number').value = doc_num;
            document.getElementById('doc_type').value = doc_type;
            document.getElementById('doc_title').value = title;
            document.getElementById('doc_source_dest').value = source_dest;
            document.getElementById('doc_date').value = doc_date;
            document.getElementById('docModalTitle').innerHTML = '<i class="fa-solid fa-pen-to-square"></i> កែប្រែព័ត៌មានលិខិតផ្លូវការ';
            openModal('addDocumentModal');
        }}
        </script>"""
        self.render_page("៥. គ្រប់គ្រងរដ្ឋបាល និងលិខិតស្នាម", content, 'documents', session_data)

    def serve_budget_assets(self, session_data):
        conn = get_db_connection()
        budgets = conn.execute('SELECT b.*, sc.name_kh as school_name FROM budgets b JOIN schools sc ON b.school_id = sc.id ORDER BY b.id DESC').fetchall()
        assets = conn.execute('SELECT a.*, sc.name_kh as school_name FROM assets a JOIN schools sc ON a.school_id = sc.id ORDER BY a.id DESC').fetchall()
        conn.close()

        b_rows = "".join([f"""<tr>
            <td><strong>{b['school_name']}</strong></td>
            <td>{b['academic_year']}</td>
            <td><span class='badge badge-gold'>{khmer_status(b['budget_type'])}</span></td>
            <td><strong style='color: var(--accent-gold);'>{b['allocated_amount']:,.0f} ៛</strong></td>
            <td>{b['spent_amount']:,.0f} ៛</td>
            <td>
                <a href="/budget_assets?action=delete&target=budget&id={b['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបថវិកានេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for b in budgets])

        a_rows = "".join([f"""<tr>
            <td><strong>{a['school_name']}</strong></td>
            <td>{a['asset_name']}</td>
            <td><span class='badge badge-primary'>{khmer_status(a['category'])}</span></td>
            <td><strong>{a['quantity']}</strong></td>
            <td><span class='badge badge-success'>{khmer_status(a['condition'])}</span></td>
            <td>
                <a href="/budget_assets?action=delete&target=asset&id={a['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបទ្រព្យសម្បត្តិនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for a in assets])

        content = f"""
        <div class="panel">
            <div class="panel-header"><div class="panel-title"><i class="fa-solid fa-wallet"></i> កញ្ចប់ថវិកាប្រតិបត្តិការសាលារៀន (PB)</div></div>
            <div class="table-responsive"><table class="custom-table"><thead><tr><th>សាលារៀន</th><th>ឆ្នាំសិក្សា</th><th>ប្រភេទ</th><th>ថវិកាទទួលបាន</th><th>ាយរួច</th><th>សកម្មភាព</th></tr></thead><tbody>{b_rows}</tbody></table></div>
        </div>
        <div class="panel">
            <div class="panel-header"><div class="panel-title"><i class="fa-solid fa-boxes-packing"></i> បញ្ជីសារពើភ័ណ្ឌ និងសម្ភារសិក្សា</div></div>
            <div class="table-responsive"><table class="custom-table"><thead><tr><th>សាលារៀន</th><th>ឈ្មោះសម្ភារ</th><th>ប្រភេទ</th><th>ចំនួន</th><th>ស្ថានភាព</th><th>សកម្មភាព</th></tr></thead><tbody>{a_rows}</tbody></table></div>
        </div>"""
        self.render_page("៦. គ្រប់គ្រងថវិកា និងទ្រព្យសម្បត្តិរដ្ឋ", content, 'budget_assets', session_data)

    def serve_reports(self, session_data):
        content = """
        <div class="panel">
            <div class="panel-header"><div class="panel-title"><i class="fa-solid fa-print"></i> ទាញយករបាយការណ៍ផ្លូវការ ផ្ញើជូនមន្ទីរអប់រំ យុវជន និងកីឡា ខេត្តសៀមរាប</div></div>
            <p style="color: var(--text-muted);">របាយការណ៍សង្ខេបអាចទាញយក ឬបោះពុម្ពបានគ្រប់ពេល។</p>
            <div style="margin-top: 20px; display: flex; gap: 16px;">
                <button class="btn btn-primary" onclick="window.print()"><i class="fa-solid fa-print"></i> បោះពុម្ពរបាយការណ៍សង្ខេប</button>
            </div>
        </div>"""
        self.render_page("៧. របាយការណ៍ និងផ្ទាំងព័ត៌មាន", content, 'reports', session_data)

    def serve_users(self, session_data):
        conn = get_db_connection()
        users = conn.execute('SELECT * FROM users ORDER BY id ASC').fetchall()
        conn.close()

        u_rows = "".join([f"""<tr>
            <td><strong>{u['username']}</strong></td>
            <td>{u['full_name']}</td>
            <td>{"<span class='badge badge-danger'><i class='fa-solid fa-crown'></i> Admin (អ្នកគ្រប់គ្រង)</span>" if u['role'] == 'admin' else ("<span class='badge badge-primary'><i class='fa-solid fa-user'></i> User (អ្នកប្រើប្រាស់)</span>" if u['role'] == 'user' else "<span class='badge badge-gold'><i class='fa-solid fa-shield'></i> Other (ផ្សេងៗ)</span>")}</td>
            <td><span class='badge badge-gold'>{u['position'] or '-'}</span></td>
            <td>{u['phone'] or '-'}</td>
            <td>
                <button class="btn btn-warning btn-sm" onclick="editUserModal('{u['id']}', '{u['username']}', '{u['full_name']}', '{u['role']}', '{u['position'] or ''}', '{u['phone'] or ''}')">
                    <i class="fa-solid fa-pen-to-square"></i> កែប្រែ
                </button>
                <a href="/users?action=delete&target=user&id={u['id']}" class="btn btn-danger btn-sm" onclick="return confirm('តើអ្នកពិតជាចង់លុបគណនីនេះមែនទេ?')">
                    <i class="fa-solid fa-trash"></i> លុប
                </a>
            </td>
        </tr>""" for u in users])

        content = f"""
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="fa-solid fa-user-shield"></i> គ្រប់គ្រងគណនី និងការកំណត់សិទ្ធិប្រើប្រាស់</div>
                <button class="btn btn-primary" onclick="openAddUserModal()">
                    <i class="fa-solid fa-user-plus"></i> បង្កើតអ្នកប្រើប្រាស់ថ្មី
                </button>
            </div>
            <div class="table-responsive">
                <table class="custom-table">
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>ឈ្មោះពេញ</th>
                            <th>Role</th>
                            <th>តំណែងមន្ត្រី</th>
                            <th>លេខទូរស័ព្ទ</th>
                            <th>សកម្មភាព</th>
                        </tr>
                    </thead>
                    <tbody>{u_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- Modal Add/Edit User -->
        <div class="modal-backdrop" id="addUserModal">
            <div class="modal-box">
                <div class="modal-header">
                    <h3 id="userModalTitle"><i class="fa-solid fa-user-plus"></i> បង្កើតគណនីអ្នកប្រើប្រាស់ថ្មី</h3>
                    <button class="modal-close" onclick="closeModal('addUserModal')">&times;</button>
                </div>
                <form action="/users/add" method="POST">
                    <input type="hidden" name="user_id" id="user_id" value="">
                    <div class="modal-body">
                        <div class="form-row">
                            <div class="form-group">
                                <label>ឈ្មោះគណនី (Username)</label>
                                <input type="text" name="username" id="user_username" class="form-control" placeholder="ឧ. officer_at" required>
                            </div>
                            <div class="form-group">
                                <label id="user_password_label">ពាក្យសម្ងាត់ (Password)</label>
                                <input type="password" name="password" id="user_password" class="form-control" placeholder="ពាក្យសម្ងាត់">
                            </div>
                        </div>

                        <div class="form-group">
                            <label>ឈ្មោះពេញ (Full Name)</label>
                            <input type="text" name="full_name" id="user_full_name" class="form-control" placeholder="ឧ. លោក សុខ ចាន់" required>
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label>សិទ្ធិប្រើប្រាស់ (Role)</label>
                                <select name="role" id="user_role" class="form-control" required>
                                    <option value="user">អ្នកប្រើប្រាស់ទូទៅ (User)</option>
                                    <option value="admin">អ្នកគ្រប់គ្រងប្រព័ន្ធ (Admin)</option>
                                    <option value="other">ផ្សេងៗ (Other)</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>តំណែងមន្ត្រី</label>
                                <div style="display: flex; gap: 6px;">
                                    <select name="position" id="user_position" class="form-control" required style="flex: 1;">
                                        <option value="ប្រធានការិយាល័យ">ប្រធានការិយាល័យ</option>
                                        <option value="អនុប្រធាន">អនុប្រធាន</option>
                                        <option value="បុគ្គលិក">បុគ្គលិក</option>
                                    </select>
                                    <button type="button" class="btn btn-secondary" onclick="addNewPositionPrompt()" style="padding: 0 14px; white-space: nowrap;" title="បន្ថែមតំណែងថ្មី">
                                        <i class="fa-solid fa-plus"></i>
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div class="form-group">
                            <label>លេខទូរស័ព្ទ</label>
                            <input type="text" name="phone" id="user_phone" class="form-control" placeholder="012 345 678">
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal('addUserModal')">បោះបង់</button>
                        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-floppy-disk"></i> រក្សាទុក</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
        function addNewPositionPrompt() {{
            var newPos = prompt("សូមបញ្ចូលឈ្មោះតំណែងមន្ត្រីថ្មី (Enter new position name):");
            if (newPos && newPos.trim() !== "") {{
                newPos = newPos.trim();
                var select = document.getElementById('user_position');
                var exists = false;
                for (var i = 0; i < select.options.length; i++) {{
                    if (select.options[i].value === newPos) {{
                        exists = true;
                        select.selectedIndex = i;
                        break;
                    }}
                }}
                if (!exists) {{
                    var opt = document.createElement('option');
                    opt.value = newPos;
                    opt.innerText = newPos;
                    select.appendChild(opt);
                    select.value = newPos;
                }}
            }}
        }}

        function openAddUserModal() {{
            document.getElementById('user_id').value = '';
            document.getElementById('user_username').value = '';
            document.getElementById('user_password').value = '';
            document.getElementById('user_password').required = true;
            document.getElementById('user_password_label').innerText = 'ពាក្យសម្ងាត់ (Password)';
            document.getElementById('user_full_name').value = '';
            document.getElementById('user_role').value = 'user';
            document.getElementById('user_position').value = 'បុគ្គលិក';
            document.getElementById('user_phone').value = '';
            document.getElementById('userModalTitle').innerHTML = '<i class="fa-solid fa-user-plus"></i> បង្កើតគណនីអ្នកប្រើប្រាស់ថ្មី';
            openModal('addUserModal');
        }}

        function editUserModal(id, username, full_name, role, position, phone) {{
            document.getElementById('user_id').value = id;
            document.getElementById('user_username').value = username;
            document.getElementById('user_password').value = '';
            document.getElementById('user_password').required = false;
            document.getElementById('user_password_label').innerText = 'ពាក្យសម្ងាត់ថ្មី (ទុកទំនេរប្រសិនបើមិនប្តូរ)';
            document.getElementById('user_full_name').value = full_name;
            document.getElementById('user_role').value = role;

            var posSelect = document.getElementById('user_position');
            if (position && position.trim() !== '') {{
                var found = false;
                for (var i = 0; i < posSelect.options.length; i++) {{
                    if (posSelect.options[i].value === position) {{
                        found = true;
                        break;
                    }}
                }}
                if (!found) {{
                    var opt = document.createElement('option');
                    opt.value = position;
                    opt.innerText = position;
                    posSelect.appendChild(opt);
                }}
                posSelect.value = position;
            }} else {{
                posSelect.value = 'បុគ្គលិក';
            }}

            document.getElementById('user_phone').value = phone;
            document.getElementById('userModalTitle').innerHTML = '<i class="fa-solid fa-user-pen"></i> កែប្រែគណនីអ្នកប្រើប្រាស់';
            openModal('addUserModal');
        }}
        </script>
        """
        self.render_page("៨. ការកំណត់សិទ្ធិប្រើប្រាស់ (User Authorization)", content, 'users', session_data)

    def serve_logs(self, session_data):
        if session_data.get('role') != 'admin':
            return self.redirect('/dashboard')

        conn = get_db_connection()
        logs = conn.execute('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 500').fetchall()
        conn.close()

        l_rows = "".join([f"""<tr>
            <td>#{l['id']}</td>
            <td><strong>{l['timestamp']}</strong></td>
            <td><strong>{l['user_name']}</strong> <span style="color: var(--text-muted); font-size: 0.85em;">({l['username']})</span></td>
            <td>
                {"<span class='badge badge-success'><i class='fa-solid fa-plus-circle'></i> បង្កើត (CREATE)</span>" if l['action_type'] == 'CREATE' else ("<span class='badge badge-gold'><i class='fa-solid fa-pen-to-square'></i> កែប្រែ (UPDATE)</span>" if l['action_type'] == 'UPDATE' else ("<span class='badge badge-danger'><i class='fa-solid fa-trash'></i> លុប (DELETE)</span>" if l['action_type'] == 'DELETE' else "<span class='badge badge-primary'><i class='fa-solid fa-right-to-bracket'></i> ចូលប្រព័ន្ធ (LOGIN)</span>"))}
            </td>
            <td><span class='badge badge-gold'>{l['module']}</span></td>
            <td>{l['details']}</td>
        </tr>""" for l in logs])

        content = f"""
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title"><i class="fa-solid fa-clock-rotate-left"></i> ៩. កំណត់ត្រាសកម្មភាព និងប្រវត្តិប្រតិបត្តិការ (Audit Logs)</div>
                <span class="badge badge-danger"><i class="fa-solid fa-user-shield"></i> សិទ្ធិតែ Admin ប៉ុណ្ណោះ</span>
            </div>
            <p style="color: var(--text-muted); margin-bottom: 16px;">តាមដានរាល់សកម្មភាពនៃការ បង្កើត (CREATE), កែប្រែ (UPDATE), និងលុប (DELETE) របស់ប្រព័ន្ធគ្រប់គ្រងការិយាល័យអប់រំ យុវជន និងកីឡា ស្រុកអង្គរធំ។</p>
            <div class="table-responsive">
                <table class="custom-table">
                    <thead>
                        <tr>
                            <th>ល.រ (ID)</th>
                            <th>កាលបរិច្ឆេទ & ម៉ោង</th>
                            <th>អ្នកប្រព្រឹត្តសកម្មភាព</th>
                            <th>ប្រភេទសកម្មភាព</th>
                            <th>មុខងារ/ម៉ូឌុល</th>
                            <th>ព័ត៌មានលម្អិត</th>
                        </tr>
                    </thead>
                    <tbody>
                        {l_rows if l_rows else '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">ពុំទាន់មានកំណត់ត្រាសកម្មភាពនៅឡើយទេ</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
        """
        self.render_page("៩. កំណត់ត្រាសកម្មភាព (Audit Logs)", content, 'logs', session_data)

def run_server():
    init_db()
    server = ReusableTCPServer(("", PORT), EduHandler)
    print(f"Angkor Thom Education Server listening on http://localhost:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
