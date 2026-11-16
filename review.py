from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

# The categories from Forró's accounts sheet ("Kontering"), plus Loan.
CATEGORIES = [
    "Entrance fee sales", "Classes sales", "Membership sales", "Workshop sales",
    "Merchandise sales", "Funds", "Marathon sales", "Group trip sales", "Food sales",
    "Festival sales", "Drinks sales", "Dance teacher costs", "Band costs",
    "Miscellaneous catering costs", "Transportation costs", "DJ costs", "Airline tickets",
    "Music equipment rental", "Purchase of electronics", "Gift cards", "Group trip costs",
    "Organizer fee costs", "Globen vouchers", "Refunds", "Discounts", "Venue costs",
    "Advertisements and advertising", "Stationery and printed matter", "Zettle fee",
    "Billetfix fee", "Mobilepay fee", "E-conomic costs", "Repair / maintenance of inventory",
    "Minor purchases", "Webpage and domain", "Bank fee", "Interest income, bank",
    "Interest expense, bank", "Returns", "Miscellaneous fees", "Shortfall",
    "Purchase of Drinks", "Loan (liability)", "Transfer between own accounts", 
]
GREY = PatternFill("solid", fgColor="EEEEEE")


def _dropdown(wb, ws, cells):
    dv = DataValidation(type="list", formula1=f"=Categories!$A$1:$A${len(CATEGORIES)}",
                        allow_blank=True, showErrorMessage=True,
                        errorTitle="Not a category", error="Choose a category from the list.")
    ws.add_data_validation(dv)
    dv.add(cells)


def write_review(bookings, path):
    """Tab 1: bookings the code could not decide. Tab 2: automatic bookings, which can be corrected."""
    wb = Workbook()
    todo = [b for b in bookings if not b["category"]]
    auto = [b for b in bookings if b["category"]]

    lists = wb.create_sheet("Categories")
    for c in sorted(CATEGORIES):
        lists.append([c])
    lists.sheet_state = "hidden"

    ws = wb.active
    ws.title = "To decide"
    ws.append(["Date", "Text", "Amount", "Category", "Comment"])
    for b in todo:
        ws.append([b["date"], b["text"], b["amount"], "", ""])
    _dropdown(wb, ws, f"D2:D{len(todo) + 1}")

    ws2 = wb.create_sheet("Booked automatically", 1)
    ws2.append(["Date", "Text", "Amount", "Category (code)", "Why", "Correct category"])
    for b in auto:
        ws2.append([b["date"], b["text"], b["amount"], b["category"], b["reason"], ""])
        for cell in ws2[ws2.max_row][:5]:
            cell.fill = GREY  # grey = written by the code
    _dropdown(wb, ws2, f"F2:F{len(auto) + 1}")

    for sheet, widths in ((ws, (12, 26, 11, 30, 30)), (ws2, (12, 26, 11, 24, 60, 26))):
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for col, width in zip("ABCDEF", widths):
            sheet.column_dimensions[col].width = width
    wb.save(path)