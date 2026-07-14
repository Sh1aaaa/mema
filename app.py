from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from dotenv import load_dotenv # Fixes the missing configuration by loading environment variables
import os

# Load environment variables from .env file immediately on startup
load_dotenv()

from payroll_engine import COAPayrollEngine
from models import MockDatabase, User
from payroll_rag import PayrollRAGEngine
from huggingface_hub import InferenceClient

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'fiscal_orchestration_fallback_key')

db = MockDatabase()
rag_engine = PayrollRAGEngine()

# Target file path directed to Vercel's writeable temporary folder sandbox
CSV_FILE_PATH = '/tmp/attendance_source.csv'
AI_MODEL_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"

HF_TOKEN = os.environ.get("HF_TOKEN")
# Fixed Initialization: Passing model name directly to prevent keyword conflicts across different versions
hf_client = InferenceClient(
    model=AI_MODEL_ID,
    token=HF_TOKEN
)

# Automatically creates the mock seed data inside /tmp on startup
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

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error_msg = None
    if request.method == 'POST':
        emp_id = request.form['employee_id']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        user = db.get_user(emp_id)
        if not user:
            error_msg = 'Employee ID not found in institutional records.'
        elif new_password != confirm_password:
            error_msg = 'Passwords do not match.'
        else:
            user.password = new_password  
            flash('Password updated successfully! Please log in with your new credentials.', 'success')
            return redirect(url_for('login'))
            
    return render_template('forgot_password.html', error=error_msg)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    role = session['role']
    user_id = session['user_id']
    csv_content = ""
    emp_record = None
    preview_data = None  # Holds temporary dry-run calculation results

    if request.method == 'POST':
        if role == 'Super Admin':
            # ACTION A: Preview calculations without mutating master files
            if 'preview_csv' in request.form:
                csv_data = request.form['csv_data']
                try:
                    TEMP_PREVIEW_PATH = '/tmp/preview_attendance.csv'
                    with open(TEMP_PREVIEW_PATH, 'w', encoding='utf-8') as f:
                        f.write(csv_data.strip())
                    
                    # Dry-run parsing through the engine
                    preview_engine = COAPayrollEngine(TEMP_PREVIEW_PATH)
                    processed_results, msg = preview_engine.validate_and_process()
                    
                    if processed_results:
                        preview_data = processed_results
                        flash("Staging dry-run completed. Review preview calculations below before committing.", "success")
                        csv_content = csv_data  # Retains modified value in text box
                    else:
                        flash(f"Engine validation failed: {msg}", "error")
                except Exception as e:
                    flash(f"System extraction error: {str(e)}", "error")

            # ACTION B: Save permanently to the HR staging files
            elif 'csv_data' in request.form:
                csv_data = request.form['csv_data']
                try:
                    with open(CSV_FILE_PATH, 'w', encoding='utf-8') as f:
                        f.write(csv_data.strip())
                    flash('Master attendance registry committed safely and sent to HR Clerk.', 'success')
                except IOError:
                    flash('Database adjustment error: File system is read-only.', 'error')
            
            # ACTION C: Approve live disbursement state
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

    # Load file contents for Super Admin edit space if not already populated by preview logic
    if role == 'Super Admin' and not csv_content and os.path.exists(CSV_FILE_PATH):
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
        emp_record=emp_record,
        preview_data=preview_data  # Pass preview context back to layout
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
        full_prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_message}\n<|assistant|>\n"
        ai_response = hf_client.text_generation(
            prompt=full_prompt,
            max_new_tokens=400,
            temperature=0.1
        )
        return jsonify({'explanation': ai_response.strip()})
    except Exception as e:
        return jsonify({'explanation': f"The RAG Desk gateway encountered an infrastructure error: {str(e)}"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
