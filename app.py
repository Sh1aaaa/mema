from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)

from payroll_engine import COAPayrollEngine
from models import MockDatabase, User
from payroll_rag import PayrollRAGEngine
from huggingface_hub import InferenceClient

import os


app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "fiscal_orchestration_fallback_key"
)


# Initialize database and RAG engine
db = MockDatabase()
rag_engine = PayrollRAGEngine()


# Vercel allows temporary file writing inside /tmp
CSV_FILE_PATH = "/tmp/attendance_source.csv"


# Hugging Face model configuration
AI_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
HF_TOKEN = os.environ.get("HF_TOKEN")


# Initialize Hugging Face client
hf_client = InferenceClient(
    provider="auto",
    api_key=HF_TOKEN
)


# Create default CSV file during startup
if not os.path.exists(CSV_FILE_PATH):
    try:
        with open(CSV_FILE_PATH, "w", encoding="utf-8") as file:
            file.write(
                "employee_id,name,daily_rate,days_worked,tardiness_mins\n"
                "1001,John Doe,600,22,30\n"
                "1002,Jane Smith,750,20,0\n"
            )

    except OSError as error:
        app.logger.error(
            "Unable to create default attendance file: %s",
            error
        )


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    error_msg = None

    if request.method == "POST":
        emp_id = request.form.get("employee_id", "").strip()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")

        if not emp_id or not name or not password:
            error_msg = "All registration fields are required."

        elif db.get_user(emp_id):
            error_msg = "Employee ID already registered."

        else:
            new_user = User(
                emp_id,
                name,
                password,
                "Employee"
            )

            db.add_user(new_user)

            flash(
                "Registration successful! Please log in.",
                "success"
            )

            return redirect(url_for("login"))

    return render_template(
        "register.html",
        error=error_msg
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error_msg = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.get_user(username)

        if user and user.verify_password(password):
            session["user_id"] = user.user_id
            session["role"] = user.role
            session["name"] = user.name

            return redirect(url_for("dashboard"))

        error_msg = "Invalid institutional credentials."

    return render_template(
        "login.html",
        error=error_msg
    )


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    error_msg = None

    if request.method == "POST":
        emp_id = request.form.get("employee_id", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        user = db.get_user(emp_id)

        if not user:
            error_msg = (
                "Employee ID not found in institutional records."
            )

        elif not new_password:
            error_msg = "New password cannot be empty."

        elif new_password != confirm_password:
            error_msg = "Passwords do not match."

        else:
            user.password = new_password

            flash(
                "Password updated successfully! "
                "Please log in with your new credentials.",
                "success"
            )

            return redirect(url_for("login"))

    return render_template(
        "forgot_password.html",
        error=error_msg
    )


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    role = session.get("role")
    user_id = str(session.get("user_id"))

    csv_content = ""
    emp_record = None

    if request.method == "POST":

        if role == "Super Admin":

            if "csv_data" in request.form:
                csv_data = request.form.get(
                    "csv_data",
                    ""
                ).strip()

                if not csv_data:
                    flash(
                        "Attendance registry cannot be empty.",
                        "error"
                    )

                else:
                    try:
                        with open(
                            CSV_FILE_PATH,
                            "w",
                            encoding="utf-8"
                        ) as file:
                            file.write(csv_data)

                        flash(
                            "Master attendance registry "
                            "updated safely.",
                            "success"
                        )

                    except OSError as error:
                        app.logger.exception(
                            "Attendance file update failed: %s",
                            error
                        )

                        flash(
                            "Database adjustment error: "
                            "Unable to update attendance file.",
                            "error"
                        )

            elif "approve_payroll" in request.form:
                db.approve_all_payroll()

                flash(
                    "Payroll records approved. "
                    "Disbursed data is now available "
                    "to institutional employees.",
                    "success"
                )

        elif role == "HR Clerk":

            if "generate_payroll" in request.form:
                try:
                    engine = COAPayrollEngine(
                        CSV_FILE_PATH
                    )

                    data, message = (
                        engine.validate_and_process()
                    )

                    if data:
                        db.update_payroll(data)

                    flash(
                        message,
                        "success" if data else "error"
                    )

                except Exception as error:
                    app.logger.exception(
                        "Payroll generation failed: %s",
                        error
                    )

                    flash(
                        "Payroll generation encountered "
                        "an unexpected error.",
                        "error"
                    )

        else:
            return (
                "Unauthorized State Mutating "
                "Action Requested.",
                403
            )

    if role == "Super Admin" and os.path.exists(
        CSV_FILE_PATH
    ):
        try:
            with open(
                CSV_FILE_PATH,
                "r",
                encoding="utf-8"
            ) as file:
                csv_content = file.read()

        except OSError as error:
            app.logger.exception(
                "Attendance registry loading failed: %s",
                error
            )

            csv_content = (
                "Error loading registry source file."
            )

    elif role == "Employee":
        raw_record = db.get_payroll_by_employee(
            user_id
        )

        if (
            raw_record
            and raw_record.get("status") == "Approved"
        ):
            emp_record = raw_record

    return render_template(
        "dashboard.html",
        session_name=session.get("name"),
        session_role=role,
        csv_content=csv_content,
        payroll_registry=db.get_all_payroll(),
        emp_record=emp_record
    )


@app.route("/audit-desk", methods=["POST"])
def audit_desk():
    if (
        "user_id" not in session
        or session.get("role") != "Employee"
    ):
        return jsonify({
            "error": "Unauthorized view configuration."
        }), 403

    request_data = request.get_json(silent=True) or {}

    user_message = str(
        request_data.get("message", "")
    ).strip()

    if not user_message:
        return jsonify({
            "error": "Message content cannot be empty."
        }), 400

    user_id = str(session.get("user_id"))
    employee_name = session.get(
        "name",
        "Employee"
    )

    emp_record = db.get_payroll_by_employee(
        user_id
    )

    payroll_context = (
        "No approved salary statement is currently "
        "released for this accounting term."
    )

    if (
        emp_record
        and emp_record.get("status") == "Approved"
    ):
        payroll_context = (
            "Active Employee Ledger Data:\n"
            f"Employee ID: {user_id}\n"
            f"Employee Name: {employee_name}\n"
            f"Gross Pay: PHP "
            f"{emp_record.get('gross_pay', 0)}\n"
            f"Total Deductions: PHP "
            f"{emp_record.get('deductions', 0)}\n"
            f"Net Take-Home Pay: PHP "
            f"{emp_record.get('net_pay', 0)}\n"
            f"Payroll Status: "
            f"{emp_record.get('status', 'Unknown')}"
        )

    try:
        retrieved_regulatory_clauses = (
            rag_engine.retrieve_relevant_context(
                user_message,
                top_k=2
            )
        )

    except Exception as error:
        app.logger.exception(
            "RAG context retrieval failed: %s",
            error
        )

        retrieved_regulatory_clauses = (
            "No regulatory clauses could be "
            "retrieved for this request."
        )

    system_prompt = (
        "You are the COA Internal Control "
        "Helpdesk Assistant.\n\n"

        f"You are talking to employee "
        f"{employee_name}.\n\n"

        "ACTIVE EMPLOYEE LEDGER DATA:\n"
        f"{payroll_context}\n\n"

        "RETRIEVED REGULATORY CLAUSES:\n"
        f"{retrieved_regulatory_clauses}\n\n"

        "INSTRUCTIONS:\n"
        "1. Answer strictly using the employee ledger "
        "data and retrieved regulatory clauses.\n"
        "2. Be helpful, precise, professional, and clear.\n"
        "3. Explain payroll calculations step by step "
        "when applicable.\n"
        "4. Do not invent deductions, regulations, "
        "policies, rates, or employee information.\n"
        "5. Do not reveal another employee's payroll data.\n"
        "6. If the answer cannot be found in the supplied "
        "context, instruct the employee to "
        "'File a Formal Revision Request' "
        "with the Super Admin."
    )

    if not HF_TOKEN:
        app.logger.error(
            "HF_TOKEN environment variable is missing."
        )

        return jsonify({
            "explanation": (
                "The RAG Engine is missing its "
                "Hugging Face authentication token."
            )
        }), 503

    try:
        response = hf_client.chat.completions.create(
            model=AI_MODEL_ID,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=400,
            temperature=0.1
        )

        ai_response = (
            response.choices[0]
            .message
            .content
        )

        if not ai_response:
            raise RuntimeError(
                "The AI provider returned "
                "an empty response."
            )

        return jsonify({
            "explanation": ai_response.strip()
        })

    except Exception as error:
        app.logger.exception(
            "Hugging Face inference failed: %s",
            error
        )

        error_text = str(error).lower()

        if (
            "failed to resolve" in error_text
            or "nameresolutionerror" in error_text
            or "name or service not known" in error_text
        ):
            message = (
                "The AI service could not be reached "
                "because of a temporary DNS or network "
                "problem. Please try again."
            )

        elif (
            "401" in error_text
            or "unauthorized" in error_text
            or "invalid token" in error_text
        ):
            message = (
                "The Hugging Face token is missing, "
                "invalid, or does not have permission "
                "to use the AI service."
            )

        elif (
            "402" in error_text
            or "payment required" in error_text
            or "credits" in error_text
        ):
            message = (
                "The Hugging Face account does not "
                "have enough inference credits."
            )

        elif (
            "403" in error_text
            or "forbidden" in error_text
        ):
            message = (
                "The Hugging Face account is not "
                "authorized to use this model."
            )

        elif (
            "404" in error_text
            or "not found" in error_text
        ):
            message = (
                "The configured AI model is unavailable "
                "or does not support this request."
            )

        elif (
            "429" in error_text
            or "too many requests" in error_text
            or "rate limit" in error_text
        ):
            message = (
                "The AI service is currently receiving "
                "too many requests. Please try again."
            )

        elif (
            "timeout" in error_text
            or "timed out" in error_text
        ):
            message = (
                "The AI service took too long to respond. "
                "Please try again."
            )

        else:
            message = (
                "The AI assistant is temporarily "
                "unavailable. Please try again later."
            )

        return jsonify({
            "explanation": message
        }), 503


@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
