# =========================================
#          IMPORTS SECTION
# =========================================
import os
import io
import json
import datetime
import re
import base64
from flask import (Flask, render_template, redirect, url_for,
                   flash, request, abort, make_response, session, jsonify)
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, login_user, current_user,
                         logout_user, login_required, UserMixin)
from flask_wtf import FlaskForm
# === Babel Imports ===
from flask_babel import Babel, _, lazy_gettext as _l, get_locale
# =====================
from wtforms import (Form, StringField, PasswordField, BooleanField,
                     SubmitField, TextAreaField, FieldList, FormField, SelectField)
from wtforms.fields import DateField
from wtforms.validators import (DataRequired, Length, EqualTo,
                            ValidationError, Optional)
from sqlalchemy import text, inspect
from werkzeug.utils import secure_filename
# === PDF and RTL Imports ===
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import arabic_reshaper
from bidi.algorithm import get_display

# ===========================
# =========================================
#          END IMPORTS SECTION
# =========================================

# --- Create Flask App Instance ---
app = Flask(__name__)

# --- App Configuration ---
app.config['SECRET_KEY'] = 'a_very_secret_key_for_development_12345'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///' + os.path.join(basedir, 'site.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'images', 'custom')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_LOGO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
app.config['AVATAR_UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'images', 'avatars')
os.makedirs(app.config['AVATAR_UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_AVATAR_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
app.config['LANGUAGES'] = {
    'en': 'English',
    'fa': 'فارسی'
}
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
# app.config['BABEL_DEFAULT_TIMEZONE'] = 'UTC'

# --- Initialize Extensions (without app object first) ---
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
babel = Babel()

# --- Define Babel Locale Selector Function ---
def select_locale():
    if 'language' in session and session['language'] in app.config['LANGUAGES'].keys():
        return session['language']
    return app.config['BABEL_DEFAULT_LOCALE']

# --- Initialize Extensions WITH App Object ---
db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)
babel.init_app(app, locale_selector=select_locale)

# --- Lightweight migration to add 'company_logo' column if missing ---
def ensure_meeting_company_logo_column():
    try:
        with app.app_context():
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('meeting')]
            if 'company_logo' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE meeting ADD COLUMN company_logo VARCHAR(255)"))
    except Exception:
        # Fail silently to avoid startup crash; user may recreate DB in dev
        pass

ensure_meeting_company_logo_column()

def ensure_meeting_company_other_name_column():
    try:
        with app.app_context():
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('meeting')]
            if 'company_other_name' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE meeting ADD COLUMN company_other_name VARCHAR(120)"))
    except Exception:
        pass

ensure_meeting_company_other_name_column()

# --- Lightweight migration for user extra columns ---
def ensure_user_extra_columns():
    try:
        with app.app_context():
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('user')]
            with db.engine.begin() as conn:
                if 'display_name' not in cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN display_name VARCHAR(50)"))
                if 'email' not in cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
                if 'avatar_path' not in cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN avatar_path VARCHAR(255)"))
    except Exception:
        pass

ensure_user_extra_columns()

# --- Font discovery helpers and context ---
def discover_fa_fonts():
    fonts_dir = os.path.join(basedir, 'static', 'fonts')
    families = {}
    if not os.path.isdir(fonts_dir):
        return families
    for fname in os.listdir(fonts_dir):
        lower = fname.lower()
        if not (lower.endswith('.woff2') or lower.endswith('.ttf')):
            continue
        # Expect pattern Family-Weight.ext
        parts = fname.rsplit('-', 1)
        if len(parts) != 2:
            continue
        family = parts[0]
        weight_part = parts[1].split('.') [0]
        weight_key = 'regular' if weight_part.lower().startswith('regular') else ('bold' if weight_part.lower().startswith('bold') else None)
        if weight_key is None:
            continue
        fam = families.setdefault(family, {})
        fam[weight_key] = fname
    return families

GOOGLE_FONTS = {
    'Inter': 'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap',
    'Roboto': 'https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap',
    'Source Sans 3': 'https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap',
    'Nunito': 'https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap',
    'Poppins': 'https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap',
}

FA_FONT_DISPLAY = {
    'Vazirmatn': 'وزیرمتن',
    'IRANYekanX': 'ایران‌یکان ایکس',
    'Dana': 'دانا',
    'PeydaWeb': 'پیدا',
    'Pelak': 'پلاک',
    'ModamWeb': 'مدام',
    'AbarMid': 'آبار مید',
}

# --- Inject locale and UI prefs into Template Context ---
@app.context_processor
def inject_locale():
    def pnum(value):
        try:
            s = str(value)
        except Exception:
            s = value
        return s.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

    current_lang = select_locale()
    ui_font_fa = session.get('ui_font_fa', 'Vazirmatn')
    ui_font_en = session.get('ui_font_en', 'Inter')
    fa_fonts = discover_fa_fonts()
    selected_fa_files = fa_fonts.get(ui_font_fa)
    fa_regular_url = None; fa_bold_url = None
    fa_regular_format = None; fa_bold_format = None
    if selected_fa_files:
        if 'regular' in selected_fa_files:
            fa_regular_url = url_for('static', filename=f"fonts/{selected_fa_files['regular']}")
            fa_regular_format = 'woff2' if selected_fa_files['regular'].lower().endswith('.woff2') else 'truetype'
        if 'bold' in selected_fa_files:
            fa_bold_url = url_for('static', filename=f"fonts/{selected_fa_files['bold']}")
            fa_bold_format = 'woff2' if selected_fa_files['bold'].lower().endswith('.woff2') else 'truetype'

    en_font_css = GOOGLE_FONTS.get(ui_font_en)

    # Build FA font options with Persian labels
    fa_fonts_options = []
    for fam in fa_fonts.keys():
        label = FA_FONT_DISPLAY.get(fam, fam)
        fa_fonts_options.append({'id': fam, 'label': label})

    return dict(
        current_locale=current_lang,
        pnum=pnum,
        ui_font_fa=ui_font_fa,
        ui_font_en=ui_font_en,
        fa_regular_url=fa_regular_url,
        fa_bold_url=fa_bold_url,
        fa_regular_format=fa_regular_format,
        fa_bold_format=fa_bold_format,
        en_font_css=en_font_css,
        available_fa_fonts=fa_fonts_options,
        available_en_fonts=list(GOOGLE_FONTS.keys()),
    )

# --- Gregorian → Jalali conversion (no extra deps) ---
def gregorian_to_jalali(gy: int, gm: int, gd: int):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd

def format_jalali(d: datetime.datetime) -> str:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return f"{jy:04d}-{jm:02d}-{jd:02d}"

# --- Helper function for RTL text processing ---
def shape_text(text):
    if text is None: return ""
    text = str(text)
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# --- Configure Login Manager ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    display_name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    avatar_path = db.Column(db.String(255), nullable=True)
    meetings = db.relationship('Meeting', backref='author', lazy=True)
    def __repr__(self): return f"User('{self.username}')"

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
# --- End Extension Initialization and Configuration ---


# === Model Definitions ===
class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    meeting_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    attendees = db.Column(db.Text, nullable=True)
    agenda = db.Column(db.Text, nullable=False)
    minutes = db.Column(db.Text, nullable=True)
    action_items = db.Column(db.Text, nullable=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company = db.Column(db.String(100), nullable=True)
    company_logo = db.Column(db.String(255), nullable=True)
    company_other_name = db.Column(db.String(120), nullable=True)
    def __repr__(self): return f"Meeting('{self.title}', '{self.meeting_date}', Company: '{self.company}')"

# === Form Definitions (Using _l directly inside class definitions) ===
class RegistrationForm(FlaskForm):
    username = StringField(_l('Username'),
                           validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    confirm_password = PasswordField(_l('Confirm Password'),
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('Sign Up'))

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError(_l('That username is already taken. Please choose a different one.'))

class LoginForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    remember = BooleanField(_l('Remember Me'))
    submit = SubmitField(_l('Login'))

class ActionItemForm(Form):
    description = TextAreaField(_l('Description'))
    assigned_to = StringField(_l('Assigned To'))
    deadline = DateField(_l('Deadline'), format='%Y-%m-%d', validators=[Optional()])

class MeetingForm(FlaskForm):
    title = StringField(_l('Title'), validators=[DataRequired()])
    meeting_date = DateField(_l('Meeting Date'), format='%Y-%m-%d', validators=[DataRequired()])
    company = SelectField(_l('Company'),
                          choices=[
                              ('', _l('-- Select Company --')),
                              ('Rabe Al Mustaqbal', _l('Rabe Al Mustaqbal')),
                              ('Rahkar Gasht', _l('Rahkar Gasht')),
                              ('EazyMig', _l('EazyMig')),
                              ('Abu Dhabi', _l('Abu Dhabi')),
                              ('Other', _l('Other'))
                          ],
                          default='',
                          validators=[Optional()])
    attendees = FieldList(StringField(_l('Attendee')), min_entries=0, label=_l('Attendees'))
    agenda_items = FieldList(StringField(_l('Agenda Item')), min_entries=0, label=_l('Agenda Items'))
    minutes = TextAreaField(_l('Minutes'))
    action_items = FieldList(
        FormField(ActionItemForm),
        min_entries=0,
        label=_l('Action Items')
    )
    submit = SubmitField(_l('Save Meeting'))


# === Route Definitions (Using _ where needed) ===
@app.route('/')
def index():
    meeting_count = 0
    recent_meetings = []
    total_actions = 0
    overdue_actions = 0
    if current_user.is_authenticated:
        user_meetings = Meeting.query.filter_by(author=current_user).order_by(Meeting.meeting_date.desc()).all()
        meeting_count = len(user_meetings)
        recent_meetings = user_meetings[:5]
        today = datetime.date.today()
        for m in user_meetings:
            try:
                items = json.loads(m.action_items or '[]')
            except Exception:
                items = []
            for it in items:
                if isinstance(it, dict):
                    total_actions += 1
                    # Skip overdue if already done
                    is_done = bool(it.get('is_done')) or str(it.get('status', '')).lower() in ('done','closed','completed','true','1')
                    if not is_done:
                        dl = it.get('deadline')
                        try:
                            if dl and datetime.date.fromisoformat(dl) < today:
                                overdue_actions += 1
                        except Exception:
                            pass
    return render_template('index.html', title=_('Home'), meeting_count=meeting_count, recent_meetings=recent_meetings, total_actions=total_actions, overdue_actions=overdue_actions)

@app.route('/set_language/<lang_code>')
def set_language(lang_code):
    if lang_code in app.config['LANGUAGES'].keys():
        session['language'] = lang_code
        flash(_('Language changed successfully.'), 'info')
    else:
        flash(_('Invalid language selected.'), 'warning')
    referrer = request.referrer
    if referrer: return redirect(referrer)
    else: return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, password_hash=hashed_password)
        db.session.add(user); db.session.commit()
        flash(_('Account created for %(username)s! You can now log in.', username=form.username.data), 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title=_('Register'), form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(_('Login Successful!'), 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else: flash(_('Login Unsuccessful. Please check username and password'), 'danger')
    return render_template('login.html', title=_('Login'), form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_('You have been logged out.'), 'success')
    return redirect(url_for('index'))

@app.route("/meeting/new", methods=['GET', 'POST'])
@login_required
def new_meeting():
    form = MeetingForm()
    if form.validate_on_submit():
        agenda_list_from_form = form.agenda_items.data; agenda_list_filtered = [item for item in agenda_list_from_form if isinstance(item, str) and item.strip()]; agenda_json_string = json.dumps(agenda_list_filtered)
        attendees_list_from_form = form.attendees.data; attendees_list_filtered = [item for item in attendees_list_from_form if isinstance(item, str) and item.strip()]; attendees_json_string = json.dumps(attendees_list_filtered)
        action_items_data = form.action_items.data; serializable_action_items = []
        for item in action_items_data:
            if isinstance(item.get('deadline'), datetime.date): item['deadline'] = item['deadline'].isoformat()
            # validate assigned_to against attendees
            if item.get('assigned_to') and item['assigned_to'] not in attendees_list_filtered:
                # If invalid, clear it
                item['assigned_to'] = ''
            serializable_action_items.append(item)
        action_items_json_string = json.dumps(serializable_action_items)
        uploaded_logo_relpath = None
        if form.company.data == 'Other':
            file = request.files.get('company_logo')
            if file and file.filename:
                filename = secure_filename(file.filename)
                name, ext = os.path.splitext(filename)
                if ext.lower() in ALLOWED_LOGO_EXTENSIONS:
                    unique_name = f"{name}_{int(datetime.datetime.utcnow().timestamp())}{ext.lower()}"
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                    file.save(save_path)
                    uploaded_logo_relpath = f"custom/{unique_name}"
        meeting = Meeting(title=form.title.data, meeting_date=form.meeting_date.data, attendees=attendees_json_string, agenda=agenda_json_string, minutes=form.minutes.data, action_items=action_items_json_string, company=form.company.data, company_logo=uploaded_logo_relpath, company_other_name=request.form.get('company_other_name') or None, author=current_user)
        db.session.add(meeting); db.session.commit()
        flash(_('Your meeting has been created!'), 'success')
        return redirect(url_for('meetings_list'))
    # Pass translated title and legend
    return render_template('create_meeting.html', title=_('New Meeting'), form=form, legend=_('New Meeting'))

@app.route("/meetings")
@login_required
def meetings_list():
    page = request.args.get('page', default=1, type=int)
    per_page = 9
    q = request.args.get('q', default='', type=str).strip()
    company_filter = request.args.get('company', default='', type=str).strip()
    date_from = request.args.get('date_from', type=str)
    date_to = request.args.get('date_to', type=str)
    status = request.args.get('status', default='', type=str).strip().lower()

    query = Meeting.query.filter_by(author=current_user)

    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Meeting.title.ilike(like), Meeting.minutes.ilike(like)))
    if company_filter:
        query = query.filter(Meeting.company == company_filter)
    try:
        if date_from:
            df = datetime.datetime.fromisoformat(date_from)
            query = query.filter(Meeting.meeting_date >= df)
    except Exception:
        pass
    try:
        if date_to:
            dt = datetime.datetime.fromisoformat(date_to) + datetime.timedelta(days=1)
            query = query.filter(Meeting.meeting_date < dt)
    except Exception:
        pass

    query = query.order_by(Meeting.meeting_date.desc())
    # Fetch all, then filter by action status in Python (JSON field)
    all_meetings = query.all()

    meetings_data_full = []
    default_logo_filename = 'default_logo.png'
    logo_mapping = {'Rabe Al Mustaqbal': 'rabe_al_mustaqbal.png','Rahkar Gasht': 'rahkar_gasht.png','EazyMig': 'eazymig.png','Abu Dhabi': 'abu_dhabi.png','Other': default_logo_filename}

    today = datetime.date.today()
    for meeting in all_meetings:
        company_name = meeting.company
        if getattr(meeting, 'company_logo', None):
            logo_filename = meeting.company_logo
        else:
        logo_filename = logo_mapping.get(company_name, default_logo_filename)
        if not logo_filename:
            logo_filename = default_logo_filename
        logo_path_check = os.path.join(basedir, 'static', 'images', logo_filename)
        if not os.path.exists(logo_path_check):
            logo_filename = default_logo_filename
            default_logo_path_check = os.path.join(basedir, 'static', 'images', default_logo_filename)
            if not os.path.exists(default_logo_path_check):
                logo_filename = None
        # Action stats per meeting
        try:
            items = json.loads(meeting.action_items or '[]')
        except Exception:
            items = []
        total_actions_m = 0
        done_actions_m = 0
        overdue_actions_m = 0
        for it in items:
            if isinstance(it, dict):
                total_actions_m += 1
                is_done = bool(it.get('is_done')) or str(it.get('status', '')).lower() in ('done','closed','completed','true','1')
                if is_done:
                    done_actions_m += 1
                else:
                    dl = it.get('deadline')
                    try:
                        if dl and datetime.date.fromisoformat(dl) < today:
                            overdue_actions_m += 1
                    except Exception:
                        pass
        # Jalali date for display (derived from Gregorian meeting_date)
        try:
            jalali_date_str = format_jalali(meeting.meeting_date)
        except Exception:
            jalali_date_str = None

        meetings_data_full.append({
            'meeting': meeting,
            'logo_filename': logo_filename,
            'company_display': meeting.company_other_name or meeting.company,
            'meeting_date_jalali': jalali_date_str,
            'total_actions': total_actions_m,
            'done_actions': done_actions_m,
            'overdue_actions': overdue_actions_m
        })

    # Apply status filter
    def match_status(d):
        if status == '' or status == 'all':
            return True
        if status == 'overdue':
            return (d['overdue_actions'] or 0) > 0
        if status == 'done':
            return (d['done_actions'] or 0) > 0
        if status == 'open':
            ta = d['total_actions'] or 0
            da = d['done_actions'] or 0
            return ta > 0 and da < ta
        return True

    meetings_data_filtered = [d for d in meetings_data_full if match_status(d)]
    total = len(meetings_data_filtered)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    meetings_data = meetings_data_filtered[start:end]
    companies = ['Rabe Al Mustaqbal', 'Rahkar Gasht', 'EazyMig', 'Abu Dhabi', 'Other']

    return render_template('meetings.html', title=_('My Meetings'), meetings_data=meetings_data,
                           page=page, total_pages=total_pages, total=total, q=q,
                           company_filter=company_filter, date_from=date_from or '', date_to=date_to or '',
                           status=status,
                           companies=companies)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        section = request.form.get('section') or ''
        lang = select_locale()
        try:
            if section == 'profile':
                current_user.display_name = (request.form.get('display_name') or '').strip() or None
                current_user.email = (request.form.get('email') or '').strip() or None
                db.session.commit()
                flash(_('Profile updated.'), 'success')
            elif section == 'password':
                current_pwd = request.form.get('current_password') or ''
                new_pwd = request.form.get('new_password') or ''
                confirm_pwd = request.form.get('confirm_password') or ''
                if not bcrypt.check_password_hash(current_user.password_hash, current_pwd):
                    flash(_('Current password is incorrect.'), 'danger')
                elif not new_pwd or new_pwd != confirm_pwd:
                    flash(_('New passwords do not match.'), 'warning')
                else:
                    current_user.password_hash = bcrypt.generate_password_hash(new_pwd).decode('utf-8')
                    db.session.commit()
                    flash(_('Password changed successfully.'), 'success')
            elif section == 'avatar':
                file = request.files.get('avatar')
                if file and file.filename:
                    name, ext = os.path.splitext(secure_filename(file.filename))
                    if ext.lower() in {'.png','.jpg','.jpeg','.webp'}:
                        unique = f"{name}_{int(datetime.datetime.utcnow().timestamp())}{ext.lower()}"
                        path = os.path.join(app.config['AVATAR_UPLOAD_FOLDER'], unique)
                        file.save(path)
                        current_user.avatar_path = f"avatars/{unique}"
                        db.session.commit()
                        flash(_('Avatar updated.'), 'success')
                    else:
                        flash(_('Invalid avatar file type.'), 'warning')
            else:
                # Fonts (existing behavior)
                if lang == 'fa':
                    chosen = request.form.get('ui_font_fa')
                    if chosen:
                        session['ui_font_fa'] = chosen
                        flash(_('Font updated successfully.'), 'success')
                else:
                    chosen = request.form.get('ui_font_en')
                    if chosen and chosen in GOOGLE_FONTS:
                        session['ui_font_en'] = chosen
                        flash(_('Font updated successfully.'), 'success')
        except Exception:
            flash(_('Something went wrong. Please try again.'), 'danger')
        return redirect(url_for('settings'))

    return render_template('settings.html', title=_('Settings'))

@app.route("/meeting/<int:meeting_id>")
@login_required
def meeting_detail(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    if meeting.author != current_user: abort(403)
    try: agenda_list = json.loads(meeting.agenda or '[]')
    except: agenda_list = []
    try: attendees_list = json.loads(meeting.attendees or '[]')
    except: attendees_list = []
    try: action_items_list = json.loads(meeting.action_items or '[]')
    except: action_items_list = []

    # Compute action item status
    today = datetime.date.today()
    total_actions = 0
    done_actions = 0
    overdue_actions = 0
    for it in action_items_list:
        if isinstance(it, dict):
            total_actions += 1
            is_done = bool(it.get('is_done')) or str(it.get('status', '')).lower() in ('done','closed','completed','true','1')
            if is_done:
                done_actions += 1
            else:
                dl = it.get('deadline')
                try:
                    if dl and datetime.date.fromisoformat(dl) < today:
                        overdue_actions += 1
                except Exception:
                    pass

    company_name = meeting.company
    default_logo_filename = 'default_logo.png'
    logo_mapping = {'Rabe Al Mustaqbal': 'rabe_al_mustaqbal.png','Rahkar Gasht': 'rahkar_gasht.png','EazyMig': 'eazymig.png','Abu Dhabi': 'abu_dhabi.png','Other': default_logo_filename}
    logo_filename = meeting.company_logo if getattr(meeting, 'company_logo', None) else logo_mapping.get(company_name, default_logo_filename)
    if not logo_filename: logo_filename = default_logo_filename
    logo_path_check = os.path.join(basedir, 'static', 'images', logo_filename)
    if not os.path.exists(logo_path_check):
        logo_filename = default_logo_filename
        default_logo_path_check = os.path.join(basedir, 'static', 'images', default_logo_filename)
        if not os.path.exists(default_logo_path_check): logo_filename = None
    # Jalali date for display
    try:
        jalali_date_str = format_jalali(meeting.meeting_date)
    except Exception:
        jalali_date_str = None
    # Title comes from DB, no need to translate here
    return render_template('meeting_detail.html', title=meeting.title, meeting=meeting, agenda_list=agenda_list, attendees_list=attendees_list, action_items_list=action_items_list, logo_filename=logo_filename, total_actions=total_actions, done_actions=done_actions, overdue_actions=overdue_actions, meeting_date_jalali=jalali_date_str)

@app.route('/meeting/<int:meeting_id>/action/<int:item_index>/toggle_done', methods=['POST'])
@login_required
def toggle_action_done(meeting_id, item_index):
    meeting = Meeting.query.get_or_404(meeting_id)
    if meeting.author != current_user:
        abort(403)
    try:
        items = json.loads(meeting.action_items or '[]')
    except Exception:
        items = []
    if not isinstance(items, list) or item_index < 0 or item_index >= len(items):
        return jsonify({'ok': False, 'error': 'index_out_of_range'}), 400
    item = items[item_index] if isinstance(items[item_index], dict) else {}
    current_done = bool(item.get('is_done')) or str(item.get('status', '')).lower() in ('done', 'closed', 'completed', 'true', '1')
    target_done = not current_done
    item['is_done'] = target_done
    item['done_at'] = datetime.datetime.utcnow().isoformat() if target_done else None
    items[item_index] = item
    meeting.action_items = json.dumps(items)
    db.session.commit()

    # recompute counters
    today = datetime.date.today()
    total = 0; done = 0; overdue = 0
    for it in items:
        if isinstance(it, dict):
            total += 1
            is_done = bool(it.get('is_done')) or str(it.get('status', '')).lower() in ('done','closed','completed','true','1')
            if is_done:
                done += 1
            else:
                dl = it.get('deadline')
                try:
                    if dl and datetime.date.fromisoformat(dl) < today:
                        overdue += 1
                except Exception:
                    pass
    return jsonify({'ok': True, 'is_done': target_done, 'counters': {'total': total, 'done': done, 'overdue': overdue}})

@app.route('/meeting/<int:meeting_id>/actions/bulk', methods=['POST'])
@login_required
def bulk_update_actions(meeting_id: int):
    meeting = Meeting.query.get_or_404(meeting_id)
    if meeting.author != current_user:
        abort(403)
    try:
        payload = request.get_json(silent=True) or {}
        indices = payload.get('indices') or []
        target_done = bool(payload.get('done'))
    except Exception:
        return jsonify({'ok': False, 'error': 'bad_request'}), 400

    try:
        items = json.loads(meeting.action_items or '[]')
    except Exception:
        items = []

    updated = []
    for idx in indices:
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            continue
        if not isinstance(items[idx], dict):
            continue
        item = items[idx]
        item['is_done'] = target_done
        item['done_at'] = datetime.datetime.utcnow().isoformat() if target_done else None
        items[idx] = item
        updated.append(idx)

    meeting.action_items = json.dumps(items)
    db.session.commit()

    # recompute counters
    today = datetime.date.today()
    total = 0; done = 0; overdue = 0
    for it in items:
        if isinstance(it, dict):
            total += 1
            is_done = bool(it.get('is_done')) or str(it.get('status', '')).lower() in ('done','closed','completed','true','1')
            if is_done:
                done += 1
            else:
                dl = it.get('deadline')
                try:
                    if dl and datetime.date.fromisoformat(dl) < today:
                        overdue += 1
                except Exception:
                    pass
    return jsonify({'ok': True, 'updated': updated, 'counters': {'total': total, 'done': done, 'overdue': overdue}, 'done': target_done})

@app.route("/meeting/<int:meeting_id>/edit", methods=['GET', 'POST'])
@login_required
def edit_meeting(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    if meeting.author != current_user: abort(403)
    form = MeetingForm()
    if form.validate_on_submit():
        # ... (POST logic) ...
        agenda_list_from_form = form.agenda_items.data; agenda_list_filtered = [item for item in agenda_list_from_form if isinstance(item, str) and item.strip()]; agenda_json_string = json.dumps(agenda_list_filtered)
        attendees_list_from_form = form.attendees.data; attendees_list_filtered = [item for item in attendees_list_from_form if isinstance(item, str) and item.strip()]; attendees_json_string = json.dumps(attendees_list_filtered)
        action_items_data = form.action_items.data; serializable_action_items = []
        for item in action_items_data:
            if isinstance(item.get('deadline'), datetime.date): item['deadline'] = item['deadline'].isoformat()
            if item.get('assigned_to') and item['assigned_to'] not in attendees_list_filtered:
                item['assigned_to'] = ''
            serializable_action_items.append(item)
        action_items_json_string = json.dumps(serializable_action_items)
        meeting.title = form.title.data; meeting.meeting_date = form.meeting_date.data; meeting.attendees = attendees_json_string; meeting.agenda = agenda_json_string; meeting.minutes = form.minutes.data; meeting.action_items = action_items_json_string; meeting.company = form.company.data; meeting.company_other_name = request.form.get('company_other_name') or meeting.company_other_name
        if form.company.data == 'Other':
            file = request.files.get('company_logo')
            if file and file.filename:
                filename = secure_filename(file.filename)
                name, ext = os.path.splitext(filename)
                if ext.lower() in ALLOWED_LOGO_EXTENSIONS:
                    unique_name = f"{name}_{int(datetime.datetime.utcnow().timestamp())}{ext.lower()}"
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                    file.save(save_path)
                    meeting.company_logo = f"custom/{unique_name}"
        db.session.commit()
        flash(_('Your meeting has been updated!'), 'success')
        return redirect(url_for('meeting_detail', meeting_id=meeting.id))
    elif request.method == 'GET':
        # ... (GET logic) ...
        try: agenda_list = json.loads(meeting.agenda or '[]')
        except: agenda_list = []
        try: attendees_list = json.loads(meeting.attendees or '[]')
        except: attendees_list = []
        try: action_items_list = json.loads(meeting.action_items or '[]')
        except: action_items_list = []
        form.title.data = meeting.title; form.meeting_date.data = meeting.meeting_date; form.minutes.data = meeting.minutes; form.company.data = meeting.company
        while form.attendees.entries: form.attendees.pop_entry()
        for attendee in attendees_list: form.attendees.append_entry(attendee)
        while form.agenda_items.entries: form.agenda_items.pop_entry()
        for item in agenda_list: form.agenda_items.append_entry(item)
        while form.action_items.entries: form.action_items.pop_entry()
        for action_item_data in action_items_list:
            if 'deadline' in action_item_data and isinstance(action_item_data['deadline'], str):
                try: action_item_data['deadline'] = datetime.date.fromisoformat(action_item_data['deadline'])
                except (ValueError, TypeError): action_item_data['deadline'] = None
            elif 'deadline' not in action_item_data or not action_item_data['deadline']: action_item_data['deadline'] = None
            form.action_items.append_entry(action_item_data)
    # Pass translated title and legend
    return render_template('create_meeting.html', title=_('Edit Meeting'), form=form, legend=_('Edit Meeting'), company_other_name=meeting.company_other_name)

@app.route("/meeting/<int:meeting_id>/delete", methods=['POST'])
@login_required
def delete_meeting(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    if meeting.author != current_user: abort(403)
    db.session.delete(meeting)
    db.session.commit()
    flash(_('Your meeting has been deleted!'), 'success')
    return redirect(url_for('meetings_list'))
# ======================================

# --- Helper function for RTL text processing (Re-added BiDi) ---
def shape_text(text):
    if text is None:
        return ""
    text = str(text) # Ensure text is string
    reshaped_text = arabic_reshaper.reshape(text)
    # === Apply BiDi algorithm ===
    bidi_text = get_display(reshaped_text)
    # ============================
    return bidi_text # Return text processed by both reshape and bidi

# --- Updated MyPDF Class with Unicode Font and Conditional RTL Alignment ---
class MyPDF(FPDF):
    def __init__(self, orientation='P', unit='mm', format='A4', meeting_title="Meeting Minutes", company_name=None, logo_path=None, lang_code='en'): # Added lang_code
        super().__init__(orientation, unit, format)
        self.meeting_title = meeting_title
        self.company_name = company_name
        self.logo_path = logo_path
        self.lang_code = lang_code # Store language code
        self.creation_datetime_obj = datetime.datetime.now()
        self.creation_date_str = self.creation_datetime_obj.strftime("%Y-%m-%d")
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(left=15, top=15, right=15)

        # Add Unicode Font
        try:
            font_regular_path = os.path.join(basedir, 'static', 'fonts', 'Vazirmatn-Regular.ttf')
            font_bold_path = os.path.join(basedir, 'static', 'fonts', 'Vazirmatn-Bold.ttf')
            if os.path.exists(font_regular_path): self.add_font('Vazirmatn', '', font_regular_path)
            else: raise FileNotFoundError("Vazirmatn-Regular.ttf not found")
            if os.path.exists(font_bold_path): self.add_font('Vazirmatn', 'B', font_bold_path)
            else: print(f"WARNING: Vazirmatn-Bold.ttf not found.")
            self.set_font('Vazirmatn', '', 9)
        except Exception as e:
             print(f"Error adding font: {e}. Falling back to default font.")
             self.set_font('Arial', '', 9)

    def header(self):
        header_start_y = self.t_margin - 5
        logo_start_x = self.l_margin + 2
        logo_start_y = header_start_y + 1
        logo_width = 35
        logo_placeholder_height = 15

        if self.logo_path and os.path.exists(self.logo_path):
            try:
                logo_placeholder_height = 20
                self.image(self.logo_path, x=logo_start_x, y=logo_start_y, w=logo_width)
            except Exception as e:
                print(f"Error adding logo in header: {e}")
                self.set_xy(logo_start_x, logo_start_y)
                self.set_font('Vazirmatn', '', 7)
                self.cell(logo_width, 8, shape_text('[Logo Error]'), border=0) # Use shape_text
                logo_placeholder_height = 8
        else: logo_placeholder_height = 5

        title_start_x = logo_start_x + logo_width + 5
        title_width = self.w - self.r_margin - title_start_x - 25
        self.set_xy(title_start_x, logo_start_y)
        self.set_font('Vazirmatn', 'B', 11)
        line_height_title = 5
        shaped_title = shape_text(self.meeting_title) # Shape title FIRST
        lines_title = len(self.multi_cell(title_width, line_height_title, shaped_title, border=0, align='C', dry_run=True, output='LINES'))
        title_actual_height = lines_title * line_height_title
        self.set_xy(title_start_x, logo_start_y)
        self.multi_cell(title_width, line_height_title, shaped_title, border=0, align='C')

        company_y = logo_start_y + title_actual_height + 1
        company_actual_height = 0
        if self.company_name:
            self.set_xy(title_start_x, company_y)
            self.set_font('Vazirmatn', '', 9)
            line_height_company = 4
            shaped_company = shape_text(self.company_name) # Shape company name
            lines_company = len(self.multi_cell(title_width, line_height_company, shaped_company, border=0, align='C', dry_run=True, output='LINES'))
            company_actual_height = lines_company * line_height_company
            self.set_xy(title_start_x, company_y)
            self.multi_cell(title_width, line_height_company, shaped_company, border=0, align='C') # Use shaped text
            company_y += company_actual_height
        else: company_y = logo_start_y + title_actual_height

        date_start_x = self.w - self.r_margin - 25
        self.set_xy(date_start_x, logo_start_y + 2)
        self.set_font('Vazirmatn', '', 9)
        self.cell(23, 5, shape_text(f"Date: {self.creation_date_str}"), border=0, align='R') # Use shape_text

        max_header_y = max(logo_start_y + logo_placeholder_height, company_y)
        self.set_y(max_header_y + 8)
        self.set_font('Vazirmatn', '', 9)

    def footer(self):
        footer_y = -15
        self.set_y(footer_y)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font('Vazirmatn', '', 8)
        self.cell(0, 4, shape_text('Powered by Rasha Press'), align='L') # Use shape_text
        self.set_x(self.w - self.r_margin - 30)
        self.set_font('Vazirmatn', '', 8)
        self.cell(0, 4, shape_text(f'Page {self.page_no()}/{{nb}}'), align='R') # Use shape_text

# --- Updated generate_meeting_pdf Function (Pyppeteer HTML->PDF) ---
# This assumes 'app' is the Flask app instance and is available in this scope
# Also assumes 'Meeting', 'db', 'basedir', '_' are defined/imported
import asyncio
from pyppeteer import launch
from pyppeteer import chromium_downloader as cd
@app.route("/meeting/<int:meeting_id>/pdf")
@login_required
def generate_meeting_pdf(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    if meeting.author != current_user:
        abort(403)

    # Prepare lists from JSON fields
    try:
        agenda_list = json.loads(meeting.agenda or '[]')
    except Exception:
        agenda_list = []
    try:
        attendees_list = json.loads(meeting.attendees or '[]')
    except Exception:
        attendees_list = []
    try:
        action_items_list = json.loads(meeting.action_items or '[]')
    except Exception:
        action_items_list = []

    # Language and direction
    lang = str(get_locale())
    text_dir = 'rtl' if lang == 'fa' else 'ltr'

    # Helper: Persian digits
    def to_persian_digits(value):
        mapping = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
        try:
            s = str(value)
        except Exception:
            s = value
        return s.translate(mapping) if lang == 'fa' else s

    # Logo mapping
    default_logo_filename = 'default_logo.png'
    logo_mapping = {
        'Rabe Al Mustaqbal': 'rabe_al_mustaqbal.png',
        'Rahkar Gasht': 'rahkar_gasht.png',
        'EazyMig': 'eazymig.png',
        'Abu Dhabi': 'abu_dhabi.png',
        'Other': default_logo_filename
    }
    # Prefer custom logo if set
    logo_filename = meeting.company_logo if getattr(meeting, 'company_logo', None) else (logo_mapping.get(meeting.company, default_logo_filename) or default_logo_filename)

    def to_file_url(path: str) -> str:
        return 'file:///' + os.path.abspath(path).replace('\\', '/')

    logo_fs_path = os.path.join(basedir, 'static', 'images', logo_filename)
    css_fs_path = os.path.join(basedir, 'static', 'css', 'pdf.css')
    # Determine UI-selected font for current language
    ui_font_fa = session.get('ui_font_fa', 'Vazirmatn')
    fa_fonts = discover_fa_fonts()
    selected_fa_files = fa_fonts.get(ui_font_fa) or {}
    # fallbacks
    font_regular_fs = os.path.join(basedir, 'static', 'fonts', selected_fa_files.get('regular') or 'Vazirmatn-Regular.ttf')
    font_bold_fs = os.path.join(basedir, 'static', 'fonts', selected_fa_files.get('bold') or 'Vazirmatn-Bold.ttf')

    def image_to_data_uri(path: str) -> str:
        try:
            ext = os.path.splitext(path)[1].lower()
            mime = 'image/png' if ext == '.png' else ('image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png')
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
                return f"data:{mime};base64,{b64}"
        except Exception:
            return None

    logo_data_uri = image_to_data_uri(logo_fs_path) if os.path.exists(logo_fs_path) else None

    # Embed fonts as base64 data URIs so Chromium always loads them offline
    def to_data_uri(path: str) -> str:
        try:
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
                return f"data:font/ttf;base64,{b64}"
        except Exception:
            return None

    # Prepare PDF font urls as data URIs to ensure loading in headless Chromium
    def font_mime_and_format(path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext == '.woff2':
            return 'font/woff2', 'woff2'
        return 'font/ttf', 'truetype'

    def to_font_data_uri(path: str):
        try:
            mime, fformat = font_mime_and_format(path)
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
                return f"data:{mime};base64,{b64}", fformat
        except Exception:
            return None, None

    pdf_font_regular_url = None
    pdf_font_bold_url = None
    pdf_font_regular_format = None
    pdf_font_bold_format = None
    if os.path.exists(font_regular_fs):
        pdf_font_regular_url, pdf_font_regular_format = to_font_data_uri(font_regular_fs)
    if os.path.exists(font_bold_fs):
        pdf_font_bold_url, pdf_font_bold_format = to_font_data_uri(font_bold_fs)

    css_text = None
    try:
        if os.path.exists(css_fs_path):
            with open(css_fs_path, 'r', encoding='utf-8') as f:
                css_text = f.read()
    except Exception:
        css_text = None

    # Prefer custom company name if present
    company_display = meeting.company_other_name or (_(meeting.company) if meeting.company else None)
    # Jalali date for PDF meta
    try:
        date_jalali = format_jalali(meeting.meeting_date)
    except Exception:
        date_jalali = None

    html = render_template(
        'pdf/meeting.html',
        meeting=meeting,
        agenda_list=agenda_list,
        attendees_list=attendees_list,
        action_items_list=action_items_list,
        text_dir=text_dir,
        lang=lang,
        company_display=company_display,
        date_jalali=date_jalali,
        pnum=to_persian_digits,
        logo_url=(logo_data_uri or (to_file_url(logo_fs_path) if os.path.exists(logo_fs_path) else None)),
        css_file_url=to_file_url(css_fs_path) if os.path.exists(css_fs_path) else None,
        pdf_font_family=('PDFAppFont'),
        pdf_font_regular_url=pdf_font_regular_url,
        pdf_font_bold_url=pdf_font_bold_url,
        pdf_font_regular_format=pdf_font_regular_format,
        pdf_font_bold_format=pdf_font_bold_format,
        css_text=css_text,
    )

    async def render_pdf(content: str) -> bytes:
        executable_path = None
        try:
            # Prefer pre-downloaded Chromium (respects PYPPETEER_HOME if set)
            path = cd.chromium_executable()
            if path and os.path.exists(path):
                executable_path = path
                else:
                # Download on-demand as a fallback
                await cd.download_chromium()
                path2 = cd.chromium_executable()
                if path2 and os.path.exists(path2):
                    executable_path = path2
        except Exception:
            executable_path = None

        launch_kwargs = dict(
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-zygote',
                '--disable-setuid-sandbox',
                '--single-process',
                '--disable-software-rasterizer',
                '--no-first-run',
                '--no-default-browser-check',
            ],
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False,
            headless=True,
        )
        if executable_path:
            launch_kwargs['executablePath'] = executable_path

        browser = await launch(**launch_kwargs)
        page = await browser.newPage()
        await page.setContent(content)
        await page.waitForSelector('body')
        pdf_bytes = await page.pdf(format='A4', margin={'top': '5mm', 'bottom': '6mm', 'left': '5mm', 'right': '5mm'}, printBackground=True)
        await browser.close()
        return pdf_bytes

    pdf_bytes = asyncio.run(render_pdf(html))

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename="meeting_report.pdf"'
    return response


# === Main Execution Block ===
if __name__ == '__main__':
    app.run(debug=True)
