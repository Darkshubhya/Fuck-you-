import requests
import json
import time
from datetime import datetime
import os
from fpdf import FPDF
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Multiple Idfy API credentials (api_key, account_id)
API_CREDENTIALS = [
    {"api_key": "4bf72ac7-f9a4-4abc-a00e-c375b2654004", "account_id": "c4cdeefb8184/419efda7-b8cf-46dc-8e5e-092989708d33"},
    {"api_key": "7e63b175-71bf-48ed-8806-ef80095697be", "account_id": "2647fe98d004/45cd6154-683f-4b73-85b4-eaaac9a5f59b"},
    # Add more key-account pairs as needed
]

# ----------------------- PDF TEMPLATE CLASS ----------------------------

class VehiclePDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, "Vehicle Verification Report", ln=True, align='C')
        self.ln(5)

    def section(self, title, fields):
        self.section_title(title)
        for label, value in fields:
            self.set_font("Arial", "B", 11)
            self.cell(60, 8, f"{label}:", border=0)
            self.set_font("Arial", "", 11)
            if label == "Address":
                self.multi_cell(0, 8, str(value or "N/A"), border=0)
            else:
                self.cell(0, 8, str(value or "N/A"), ln=True, border=0)
        self.ln(2)

    def section_title(self, title):
        self.set_fill_color(230, 230, 230)
        self.set_font("Arial", "B", 13)
        self.cell(0, 10, title, ln=True, fill=True)
        self.ln(1)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cell(0, 10, f"Data via @ Vedant Hondre | Generated: {now}", align='C')

    def build(self, data):
        self.add_page()
        self.section("OWNER DETAILS", [
            ("Owner Name", data.get("owner_name")),
            ("Father Name", data.get("father_name")),
            ("Address", data.get("permanent_address")),
            ("Mobile Number", data.get("owner_mobile_no"))
        ])
        self.section("VEHICLE INFORMATION", [
            ("Registration No.", data.get("registration_number")),
            ("Manufacturer", data.get("manufacturer")),
            ("Model", data.get("manufacturer_model")),
            ("Fuel Type", data.get("fuel_type")),
            ("Colour", data.get("colour")),
            ("RC Status", data.get("status_verification")),
            ("RTO Office", f"{data.get('registered_place')}, {data.get('state')}"),
            ("Registration Date", data.get("registration_date")),
            ("Fitness Upto", data.get("fitness_upto")),
            ("Vehicle Class", data.get("vehicle_class")),
        ])
        self.section("INSURANCE & REGISTRATION", [
            ("Insurance Company", data.get("insurance_name")),
            ("Insurance Validity", data.get("insurance_validity")),
            ("Insurance Policy No", data.get("insurance_policy_no")),
            ("PUC Valid Upto", data.get("puc_valid_upto")),
            ("PUC No.", data.get("puc_number")),
        ])
        self.section("TECHNICAL DETAILS", [
            ("Manufacturing Date", data.get("m_y_manufacturing")),
            ("Body Type", data.get("body_type")),
            ("Wheelbase", f"{data.get('wheelbase')} mm"),
            ("GVW", f"{data.get('gross_vehicle_weight')} kg"),
            ("Cubic Capacity", f"{data.get('cubic_capacity')} cc"),
            ("Norms", data.get("norms_type")),
            ("Seating Capacity", data.get("seating_capacity")),
        ])
        self.section("ENGINE & CHASSIS", [
            ("Engine Number", data.get("engine_number")),
            ("Chassis Number", data.get("chassis_number")),
        ])

# ------------------------ FORMATTED TELEGRAM MESSAGE ------------------------

def format_message(data):
    return f"""
🚘 *Vehicle Trace Result*:

╭───❖ 👤 *Owner Info* ❖───╮
├ 👤 Owner Name: {data.get('owner_name', 'N/A')}
├ 🧔 Father Name: {data.get('father_name', 'N/A')}
├ 🏠 Permanent Address: {data.get('permanent_address', 'N/A')}
└ 🏡 Present Address: {data.get('present_address', data.get('permanent_address', 'N/A'))}

╭───❖ 🚗 *Vehicle Info* ❖───╮
├ 🆔 Registration No: {data.get('registration_number', 'N/A')}
├ 🛠️ Manufacturer: {data.get('manufacturer', 'N/A')}
├ 📛 Model: {data.get('manufacturer_model', 'N/A')}
├ 🚗 Vehicle Class: {data.get('vehicle_class', 'N/A')}
├ ⛽ Fuel Type: {data.get('fuel_type', 'N/A')}
├ 🎨 Colour: {data.get('colour', 'N/A')}
├ 🔧 Body Type: {data.get('body_type', 'N/A')}
├ 🛞 Wheelbase: {data.get('wheelbase', 'N/A')} mm
└ ⚖️ GVW: {data.get('gross_vehicle_weight', 'N/A')} kg

╭───❖ 🗓️ *Registration Info* ❖───╮
├ 📅 MFG Date: {data.get('m_y_manufacturing', 'N/A')}
├ 📜 RC Status: {data.get('status_verification', 'N/A')}
├ 🏢 RTO Office: {data.get('registered_place', 'N/A')}, {data.get('state', 'N/A')}
├ 📆 Registration Date: {data.get('registration_date', 'N/A')}
└ 🧾 Fitness Upto: {data.get('fitness_upto', 'N/A')}

╭───❖ 🛡️ *Insurance Info* ❖───╮
├ 🏦 Insurer: {data.get('insurance_name', 'N/A')}
├ 📅 Valid Upto: {data.get('insurance_validity', 'N/A')}
└ 🆔 Policy No: {data.get('insurance_policy_no', 'N/A')}

╭───❖ ⚙️ *Engine & Chassis* ❖───╮
├ 🔢 Engine No: {data.get('engine_number', 'N/A')}
└ 🔑 Chassis No: {data.get('chassis_number', 'N/A')}
"""

# ----------------------- DATA FETCH & PDF GEN ------------------------

async def fetch_vehicle_data(rc_number):
    for creds in API_CREDENTIALS:
        headers = {
            'api-key': creds["api_key"],
            'account-id': creds["account_id"],
            'Content-Type': 'application/json'
        }
        try:
            payload = json.dumps({
                "task_id": "74f4c926-250c-43ca-9c53-453e87ceacd1",
                "group_id": "8e16424a-58fc-4ba4-ab20-5bc8e7c3c41e",
                "data": {"rc_number": rc_number}
            })
            post_url = "https://eve.idfy.com/v3/tasks/async/verify_with_source/ind_rc_plus"
            post_response = requests.post(post_url, headers=headers, data=payload, timeout=10)
            post_result = post_response.json()
            request_id = post_result.get("request_id")

            if not request_id:
                continue

            time.sleep(3)
            get_url = f"https://eve.idfy.com/v3/tasks?request_id={request_id}"
            get_response = requests.get(get_url, headers=headers, timeout=10)
            result_data = get_response.json()

            if result_data and isinstance(result_data, list):
                return result_data[0]["result"]["extraction_output"], None

        except Exception:
            continue

    return None, "❌ Unable to fetch vehicle details at the moment. Please try again later."

def generate_pdf(data, rc_number):
    filename = f"RC_Report_{rc_number}.pdf"
    filepath = os.path.join(os.getcwd(), filename)
    pdf = VehiclePDF()
    pdf.build(data)
    pdf.output(filepath)
    return filepath

# --------------------------- TELEGRAM BOT ----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔰 Send me a vehicle number (e.g. HR51AF4747) to get RC details and a downloadable PDF report.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rc_number = update.message.text.strip().upper()
    await update.message.reply_text("⏳ Fetching vehicle details...")

    data, error = await fetch_vehicle_data(rc_number)
    if error:
        await update.message.reply_text(error)
        return

    message = format_message(data)
    await update.message.reply_text(message, parse_mode='Markdown')

    pdf_path = generate_pdf(data, rc_number)
    await update.message.reply_document(open(pdf_path, "rb"), filename=f"{rc_number}_Report.pdf")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
