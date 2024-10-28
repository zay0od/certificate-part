from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from io import BytesIO
import os
import logging
from werkzeug.middleware.proxy_fix import ProxyFix
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.wsgi_app = ProxyFix(app.wsgi_app)

# Configuration
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'static', 'certEnPDF.pdf')
FONT_PATH = os.path.join(os.path.dirname(__file__), 'fonts', 'Cairo-SemiBold.ttf')  # Changed to directly use bold font
HTML_PATH = 'certificate_generator.html'

def init_app():
    """Initialize application resources."""
    try:
        # Verify template file exists
        if not os.path.exists(TEMPLATE_PATH):
            raise FileNotFoundError(f"Certificate template not found at {TEMPLATE_PATH}")
        
        # Verify font file exists
        if not os.path.exists(FONT_PATH):
            raise FileNotFoundError(f"Font file not found at {FONT_PATH}")
        
        # Register the font
        pdfmetrics.registerFont(TTFont('Cairo-SemiBold.ttf', FONT_PATH))
            
        # Verify HTML file exists
        if not os.path.exists(HTML_PATH):
            raise FileNotFoundError(f"HTML file not found at {HTML_PATH}")
            
        logger.info("Application initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

def get_pdf_dimensions(pdf_path):
    """Get the dimensions of the template PDF."""
    try:
        reader = PdfReader(pdf_path)
        page = reader.pages[0]
        return (float(page.mediabox.width), float(page.mediabox.height))
    except Exception as e:
        logger.error(f"Failed to get PDF dimensions: {str(e)}")
        return A4

def format_name(name):
    """
    Format the name with proper capitalization.
    Handles multiple spaces and special cases.
    """
    # Split the name into parts while handling multiple spaces
    name_parts = [part for part in name.split() if part]
    
    # Title case each part
    formatted_parts = []
    for part in name_parts:
        # Handle special cases like "de" "van" "al" etc if needed
        formatted_parts.append(part.capitalize())
    
    # Join the parts with a single space
    return ' '.join(formatted_parts)

@app.route('/')
def index():
    """Serve the certificate generator HTML page."""
    try:
        return send_file(HTML_PATH)
    except Exception as e:
        logger.error(f"Failed to serve index page: {str(e)}")
        return jsonify({"error": "Failed to load page"}), 500

@app.route('/generate_certificate', methods=['POST'])
def generate_certificate():
    """Generate a PDF certificate based on the provided name."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        name = data.get('name')
        
        if not name:
            return jsonify({"error": "Name is required"}), 400
        
        # Sanitize and format the name
        name = format_name(name.strip())
        if len(name) > 100:
            return jsonify({"error": "Name is too long"}), 400

        # Get template dimensions
        template_width, template_height = get_pdf_dimensions(TEMPLATE_PATH)

        # Create a new PDF with reportlab using template dimensions
        temp_buffer = BytesIO()
        c = canvas.Canvas(temp_buffer, pagesize=(template_width, template_height))
        
        # Configure text properties
        font_name = "Cairo-SemiBold.ttf"
        font_size = 43
        c.setFont(font_name, font_size)
        
        # Get the width of the name text
        name_width = c.stringWidth(name, font_name, font_size)
        
        # Calculate center position
        x_position = (template_width - name_width) / 2
        y_position = (template_height / 2) - 30  # Adjust this value to move text up/down
        
        # Draw the name
        c.drawString(x_position, y_position, name)
        c.save()
        
        # Create a new PDF that combines the template and the name
        output_buffer = BytesIO()
        
        # Open the template PDF
        template_pdf = PdfReader(TEMPLATE_PATH)
        output_pdf = PdfWriter()

        # Get the first page of the template
        template_page = template_pdf.pages[0]
        
        # Get the page with the name
        temp_buffer.seek(0)
        name_pdf = PdfReader(temp_buffer)
        name_page = name_pdf.pages[0]
        
        # Merge the pages
        template_page.merge_page(name_page)
        output_pdf.add_page(template_page)
        
        # Write the result to the output buffer
        output_pdf.write(output_buffer)
        output_buffer.seek(0)
        
        # Send the final PDF
        return send_file(
            output_buffer,
            as_attachment=True,
            download_name=f"{name}_certificate.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Failed to generate certificate: {str(e)}")
        return jsonify({"error": "Failed to generate certificate"}), 500

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500

# Initialize the application
try:
    init_app()
except Exception as e:
    logger.critical(f"Failed to start application: {str(e)}")
    exit(1)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )