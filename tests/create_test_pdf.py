from reportlab.pdfgen import canvas

def create_test_pdf():
    c = canvas.Canvas("tests/test_files/test.pdf")
    c.drawString(100, 750, "Test PDF Content")
    c.save()

if __name__ == "__main__":
    create_test_pdf() 