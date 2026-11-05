from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import init_db, get_db
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'change-this-secret-before-deployment'
init_db()


def current_user():
    if 'user_id' not in session:
        return None
    db = get_db()
    user = db.execute('SELECT id,name,email,role,room FROM users WHERE id=?', (session['user_id'],)).fetchone()
    db.close()
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for('login'))
            if user['role'] not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco

@app.context_processor
def inject_user():
    return {'me': current_user(), 'now_year': datetime.now().year}

@app.route('/')
def index():
    db=get_db()
    notices=db.execute('SELECT * FROM notices ORDER BY created_at DESC LIMIT 5').fetchall()
    db.close()
    return render_template('index.html', notices=notices)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower()
        password=request.form.get('password',''); room=request.form.get('room','').strip()
        if not name or not email or len(password)<6:
            flash('Enter all details. Password must be at least 6 characters.', 'danger')
        else:
            db=get_db()
            try:
                db.execute('INSERT INTO users(name,email,password_hash,role,room) VALUES(?,?,?,?,?)',(name,email,generate_password_hash(password),'student',room))
                db.commit(); flash('Registration successful. Please log in.','success'); return redirect(url_for('login'))
            except Exception:
                flash('That email may already be registered.','danger')
            finally: db.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        db=get_db(); user=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); db.close()
        if user and check_password_hash(user['password_hash'],password):
            session.clear(); session['user_id']=user['id']; flash(f'Welcome, {user["name"]}!','success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('You have logged out.','info'); return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    u=current_user(); db=get_db()
    if u['role'] in ('admin','warden'):
        stats={
          'open_complaints':db.execute("SELECT COUNT(*) n FROM complaints WHERE status!='Resolved'").fetchone()['n'],
          'resources':db.execute("SELECT COUNT(*) n FROM resources WHERE status='Available'").fetchone()['n'],
          'lost_items':db.execute("SELECT COUNT(*) n FROM lost_found WHERE status='Open'").fetchone()['n'],
          'students':db.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()['n']}
    else:
        stats={'my_complaints':db.execute('SELECT COUNT(*) n FROM complaints WHERE user_id=?',(u['id'],)).fetchone()['n'],
          'my_requests':db.execute('SELECT COUNT(*) n FROM resource_requests WHERE requester_id=?',(u['id'],)).fetchone()['n'],
          'resources':db.execute("SELECT COUNT(*) n FROM resources WHERE status='Available'").fetchone()['n'],
          'lost_items':db.execute("SELECT COUNT(*) n FROM lost_found WHERE status='Open'").fetchone()['n']}
    notices=db.execute('SELECT * FROM notices ORDER BY created_at DESC LIMIT 4').fetchall(); db.close()
    return render_template('dashboard.html',stats=stats,notices=notices)

@app.route('/resources')
def resources():
    q=request.args.get('q','').strip(); category=request.args.get('category','')
    db=get_db(); sql='''SELECT r.*,u.name owner_name FROM resources r JOIN users u ON u.id=r.owner_id WHERE r.status='Available' '''; args=[]
    if q: sql+=' AND (r.title LIKE ? OR r.description LIKE ?)'; args += [f'%{q}%',f'%{q}%']
    if category: sql+=' AND r.category=?'; args.append(category)
    items=db.execute(sql+' ORDER BY r.created_at DESC',args).fetchall(); db.close()
    return render_template('resources.html',items=items,q=q,category=category)

@app.route('/resources/add', methods=['GET','POST'])
@login_required
def add_resource():
    if request.method=='POST':
        title=request.form.get('title','').strip(); category=request.form.get('category','Other'); description=request.form.get('description','').strip(); kind=request.form.get('kind','Borrow')
        if not title: flash('Item name is required.','danger')
        else:
            db=get_db(); db.execute('INSERT INTO resources(owner_id,title,category,description,kind,status) VALUES(?,?,?,?,?,?)',(session['user_id'],title,category,description,kind,'Available')); db.commit(); db.close()
            flash('Resource posted. Students can now find it.','success'); return redirect(url_for('resources'))
    return render_template('add_resource.html')

@app.route('/resources/<int:item_id>/request',methods=['POST'])
@login_required
def request_resource(item_id):
    db=get_db(); item=db.execute("SELECT * FROM resources WHERE id=? AND status='Available'",(item_id,)).fetchone()
    if not item: db.close(); flash('This item is no longer available.','warning'); return redirect(url_for('resources'))
    if item['owner_id']==session['user_id']: db.close(); flash('You cannot request your own item.','warning'); return redirect(url_for('resources'))
    try:
        db.execute('INSERT INTO resource_requests(resource_id,requester_id,message,status) VALUES(?,?,?,?)',(item_id,session['user_id'],request.form.get('message','').strip(),'Pending'))
        db.commit(); flash('Request sent to the item owner.','success')
    except Exception: flash('You already have an active request for this item.','warning')
    db.close(); return redirect(url_for('my_requests'))

@app.route('/my-requests')
@login_required
def my_requests():
    db=get_db(); rows=db.execute('''SELECT rr.*,r.title,r.owner_id,u.name requester FROM resource_requests rr JOIN resources r ON r.id=rr.resource_id JOIN users u ON u.id=rr.requester_id WHERE rr.requester_id=? OR r.owner_id=? ORDER BY rr.created_at DESC''',(session['user_id'],session['user_id'])).fetchall(); db.close()
    return render_template('my_requests.html',rows=rows)

@app.route('/requests/<int:req_id>/status',methods=['POST'])
@login_required
def request_status(req_id):
    status=request.form.get('status','Pending'); db=get_db()
    row=db.execute('SELECT rr.*,r.owner_id FROM resource_requests rr JOIN resources r ON r.id=rr.resource_id WHERE rr.id=?',(req_id,)).fetchone()
    if not row: db.close(); abort(404)
    if row['owner_id']!=session['user_id'] and current_user()['role'] not in ('admin','warden'): db.close(); abort(403)
    if status not in ('Pending','Approved','Rejected','Returned'): db.close(); abort(400)
    db.execute('UPDATE resource_requests SET status=? WHERE id=?',(status,req_id))
    if status=='Approved': db.execute("UPDATE resources SET status='Borrowed' WHERE id=?",(row['resource_id'],))
    if status=='Returned': db.execute("UPDATE resources SET status='Available' WHERE id=?",(row['resource_id'],))
    db.commit(); db.close(); flash('Request status updated.','success'); return redirect(url_for('my_requests'))

@app.route('/complaints',methods=['GET','POST'])
@login_required
def complaints():
    db=get_db()
    if request.method=='POST':
        title=request.form.get('title','').strip(); category=request.form.get('category','Other'); description=request.form.get('description','').strip(); priority=request.form.get('priority','Normal')
        if not title or not description: flash('Add a title and description.','danger')
        else:
            # Simple duplicate detection: same user, category, title, unresolved complaint.
            duplicate=db.execute('SELECT id FROM complaints WHERE user_id=? AND category=? AND lower(title)=lower(?) AND status!=\'Resolved\'',(session['user_id'],category,title)).fetchone()
            if duplicate: flash(f'A similar unresolved complaint already exists (#{duplicate["id"]}).','warning')
            else:
                db.execute('INSERT INTO complaints(user_id,title,category,description,priority,status) VALUES(?,?,?,?,?,?)',(session['user_id'],title,category,description,priority,'Pending')); db.commit(); flash('Complaint submitted to hostel management.','success'); db.close(); return redirect(url_for('complaints'))
    u=current_user()
    if u['role'] in ('admin','warden'):
        rows=db.execute("SELECT c.*,u.name,u.room FROM complaints c JOIN users u ON u.id=c.user_id ORDER BY CASE c.priority WHEN 'Urgent' THEN 0 WHEN 'High' THEN 1 ELSE 2 END,c.created_at DESC").fetchall()
    else: rows=db.execute('SELECT c.*,u.name,u.room FROM complaints c JOIN users u ON u.id=c.user_id WHERE c.user_id=? ORDER BY c.created_at DESC',(u['id'],)).fetchall()
    db.close(); return render_template('complaints.html',rows=rows)

@app.route('/complaints/<int:complaint_id>/status',methods=['POST'])
@roles_required('admin','warden')
def complaint_status(complaint_id):
    status=request.form.get('status','Pending')
    if status not in ('Pending','In Progress','Resolved'): abort(400)
    db=get_db(); db.execute('UPDATE complaints SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(status,complaint_id)); db.commit(); db.close()
    flash('Complaint status updated.','success'); return redirect(url_for('complaints'))

@app.route('/lost-found',methods=['GET','POST'])
@login_required
def lost_found():
    db=get_db()
    if request.method=='POST':
        title=request.form.get('title','').strip(); kind=request.form.get('kind','Lost'); location=request.form.get('location','').strip(); description=request.form.get('description','').strip(); contact=request.form.get('contact','').strip()
        if title and location:
            db.execute('INSERT INTO lost_found(user_id,title,kind,location,description,contact,status) VALUES(?,?,?,?,?,?,?)',(session['user_id'],title,kind,location,description,contact,'Open')); db.commit(); flash('Lost/found post added.','success'); db.close(); return redirect(url_for('lost_found'))
        flash('Item name and location are required.','danger')
    rows=db.execute("SELECT lf.*,u.name FROM lost_found lf JOIN users u ON u.id=lf.user_id ORDER BY CASE lf.status WHEN 'Open' THEN 0 ELSE 1 END,lf.created_at DESC").fetchall(); db.close()
    return render_template('lost_found.html',rows=rows)

@app.route('/lost-found/<int:item_id>/resolve',methods=['POST'])
@login_required
def resolve_lost(item_id):
    db=get_db(); row=db.execute('SELECT * FROM lost_found WHERE id=?',(item_id,)).fetchone()
    if not row: db.close(); abort(404)
    if row['user_id']!=session['user_id'] and current_user()['role'] not in ('admin','warden'): db.close(); abort(403)
    db.execute("UPDATE lost_found SET status='Resolved' WHERE id=?",(item_id,)); db.commit(); db.close(); flash('Post marked resolved.','success'); return redirect(url_for('lost_found'))

@app.route('/mess',methods=['GET','POST'])
@login_required
def mess():
    db=get_db()
    if request.method=='POST':
        if current_user()['role'] not in ('admin','warden'): abort(403)
        day=request.form.get('day','').strip(); breakfast=request.form.get('breakfast','').strip(); lunch=request.form.get('lunch','').strip(); dinner=request.form.get('dinner','').strip()
        if day and breakfast and lunch and dinner:
            db.execute('INSERT INTO mess_menu(day,breakfast,lunch,dinner,created_by) VALUES(?,?,?,?,?)',(day,breakfast,lunch,dinner,session['user_id'])); db.commit(); flash('Mess menu published.','success')
    menus=db.execute('SELECT * FROM mess_menu ORDER BY id DESC LIMIT 14').fetchall()
    feedback=db.execute('SELECT f.*,u.name FROM mess_feedback f JOIN users u ON u.id=f.user_id ORDER BY f.created_at DESC LIMIT 20').fetchall() if current_user()['role'] in ('admin','warden') else []
    db.close(); return render_template('mess.html',menus=menus,feedback=feedback)

@app.route('/mess/feedback',methods=['POST'])
@login_required
def mess_feedback():
    rating=request.form.get('rating','3'); comment=request.form.get('comment','').strip()
    try: rating=max(1,min(5,int(rating)))
    except ValueError: rating=3
    db=get_db(); db.execute('INSERT INTO mess_feedback(user_id,rating,comment) VALUES(?,?,?)',(session['user_id'],rating,comment)); db.commit(); db.close(); flash('Mess feedback submitted.','success'); return redirect(url_for('mess'))

@app.route('/notices',methods=['GET','POST'])
def notices():
    db=get_db()
    if request.method=='POST':
        if not current_user() or current_user()['role'] not in ('admin','warden'): abort(403)
        title=request.form.get('title','').strip(); body=request.form.get('body','').strip()
        if title and body: db.execute('INSERT INTO notices(title,body,created_by) VALUES(?,?,?)',(title,body,session['user_id'])); db.commit(); flash('Notice published.','success')
    rows=db.execute('SELECT n.*,u.name author FROM notices n JOIN users u ON u.id=n.created_by ORDER BY n.created_at DESC').fetchall(); db.close(); return render_template('notices.html',rows=rows)

@app.route('/admin')
@roles_required('admin','warden')
def admin():
    db=get_db(); stats={
      'students':db.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()['n'],
      'complaints':db.execute("SELECT COUNT(*) n FROM complaints WHERE status!='Resolved'").fetchone()['n'],
      'urgent':db.execute("SELECT COUNT(*) n FROM complaints WHERE priority='Urgent' AND status!='Resolved'").fetchone()['n'],
      'available':db.execute("SELECT COUNT(*) n FROM resources WHERE status='Available'").fetchone()['n'],
      'lost':db.execute("SELECT COUNT(*) n FROM lost_found WHERE status='Open'").fetchone()['n']}
    latest=db.execute('SELECT c.*,u.name,u.room FROM complaints c JOIN users u ON u.id=c.user_id ORDER BY c.created_at DESC LIMIT 8').fetchall(); db.close()
    return render_template('admin.html',stats=stats,latest=latest)

@app.route('/admin/students')
@roles_required('admin','warden')
def registered_students():
    q = request.args.get('q', '').strip()
    db = get_db()
    sql = "SELECT id, name, email, room, created_at FROM users WHERE role='student'"
    args = []
    if q:
        sql += " AND (name LIKE ? OR email LIKE ? OR room LIKE ?)"
        args.extend([f'%{q}%', f'%{q}%', f'%{q}%'])
    sql += " ORDER BY name "
    students = db.execute(sql, args).fetchall()
    total = db.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()['n']
    db.close()
    return render_template('students.html', students=students, q=q, total=total)

@app.errorhandler(403)
def forbidden(e): return render_template('error.html',code=403,message='You do not have permission to do that.'),403
@app.errorhandler(404)
def not_found(e): return render_template('error.html',code=404,message='Page or item not found.'),404

if __name__=='__main__':
    app.run(debug=True)


