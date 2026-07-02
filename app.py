from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from payroll_engine import COAPayrollEngine
from models import MockDatabase, User
from payroll_rag import PayrollRAGEngine
from huggingface_hub import InferenceClient
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'fiscal_orchestration_fallback_key')

db = MockDatabase()
rag_engine = PayrollRAGEngine()

# FIX: Moved the target file path to Vercel's writeable temporary folder sandbox
CSV_FILE_PATH = '/tmp/attendance_source.csv'
AI_MODEL_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"

HF_TOKEN = os.environ.get("HF_TOKEN")
hf_client = InferenceClient(
    model=AI_MODEL_ID,
    token=HF_TOKEN
)

# FIX: Automatically creates the mock seed data inside /tmp on startup so the engine doesn't crash
if not os.path.exists(CSV_FILE_PATH):
    try:
        with open(CSV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("employee_id,name,daily_rate,days_worked,tardiness_mins\n1001,John Doe,600,22,30\n1002,Jane Smith,750,20,0\n")
    except IOError:
        pass

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error_msg = None
    if request.method == 'POST':
        emp_id = request.form['employee_id']
        name = request.form['name']
        password = request.form['password']

        if db.get_user(emp_id):
            error_msg = 'Employee ID already registered.'
        else:
            new_user = User(emp_id, name, password, 'Employee')
            db.add_user(new_user)
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', error=error_msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error_msg = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = db.get_user(username)
        if user and user.verify_password(password):
            session['user_id'] = user.user_id
            session['role'] = user.role
            session['name'] = user.name
            return redirect(url_for('dashboard'))
        error_msg = 'Invalid institutional credentials.'
    return render_template('login.html', error=error_msg)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    role = session['role']
    user_id = session['user_id']
    csv_content = ""
    emp_record = None

    if request.method == 'POST':
        if role == 'Super Admin':
            if 'csv_data' in request.form:
                csv_data = request.form['csv_data']
                try:
                    with open(CSV_FILE_PATH, 'w', encoding='utf-8') as f:
                        f.write(csv_data.strip())
                    flash('Master attendance registry updated safely.', 'success')
                except IOError:
                    flash('Database adjustment error: File system is read-only.', 'error')
            elif 'approve_payroll' in request.form:
                db.approve_all_payroll()
                flash('Payroll records approved. Disbursed data is now live for institutional employees.', 'success')
        elif role == 'HR Clerk':
            if 'generate_payroll' in request.form:
                engine = COAPayrollEngine(CSV_FILE_PATH)
                data, msg = engine.validate_and_process()
                if data:
                    db.update_payroll(data)
                flash(msg, 'success' if data else 'error')
        else:
            return "Unauthorized State Mutating Action Requested.", 403

    if role == 'Super Admin' and os.path.exists(CSV_FILE_PATH):
        try:
            with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
                csv_content = f.read()
        except IOError:
            csv_content = "Error loading registry source file."
    elif role == 'Employee':
        raw_record = db.get_payroll_by_employee(user_id)
        if raw_record and raw_record.get('status') == 'Approved':
            emp_record = raw_record

    return render_template(
        'dashboard.html',
        session_name=session['name'],
        session_role=role,
        csv_content=csv_content,
        payroll_registry=db.get_all_payroll(),
        emp_record=emp_record
    )

@app.route('/audit-desk', methods=['POST'])
def audit_desk():
    if 'user_id' not in session or session.get('role') != 'Employee':
        return jsonify({'error': 'Unauthorized view configuration.'}), 403

    user_message = request.json.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'Message content cannot be empty.'}), 400

    user_id = str(session['user_id'])
    emp_record = db.get_payroll_by_employee(user_id)

    payroll_context = "No approved salary statement currently released for this accounting term."
    if emp_record:
        payroll_context = (
            f"Active Employee Ledger Data: ID={user_id}, Name={session['name']}. "
            f"Gross Pay: PHP {emp_record['gross_pay']}, Total Deductions: PHP {emp_record['deductions']}, "
            f"Net Disbursed Take-Home Pay: PHP {emp_record['net_pay']}. Status: {emp_record['status']}."
        )

    retrieved_regulatory_clauses = rag_engine.retrieve_relevant_context(user_message, top_k=2)

    system_prompt = (
        f"You are the COA Internal Control Helpdesk Assistant. You are talking to employee {session['name']}.\n"
        f"Here is their real system context data:\n{payroll_context}\n\n"
        f"Here are the authoritative regulatory rules retrieved dynamically for this query:\n"
        f"{retrieved_regulatory_clauses}\n\n"
        "Ground your conversation strictly on the active ledger data and retrieved clauses provided above. "
        "Be helpful, precise, and professional. Explain calculations clearly using only these metrics. "
        "Do not invent external rules. If a resolution cannot be found in the context data, instruct them to 'File a Formal Revision Request' with the Super Admin."
    )

    if not HF_TOKEN:
        return jsonify({'explanation': "The RAG Engine is missing authentication configurations."})

    try:
        completion = hf_client.chat.completions.create(
            model=AI_MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=400,
            temperature=0.1
        )
        ai_response = completion.choices[0].message.content
        return jsonify({'explanation': ai_response})
    except Exception as e:
        return jsonify({'explanation': f"The RAG Desk gateway encountered an infrastructure error: {str(e)}"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
