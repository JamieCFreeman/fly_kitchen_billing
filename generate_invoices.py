#!/usr/bin/env python3
"""Generate per-user PDF invoices from a charge dataframe.

Usage:
  python generate_invoices.py --input charges.csv --output ./invoices

You can run this after billing_from_gsheet.py by exporting charge_df to CSV:
  charge_df.to_csv('charges.csv', index=False)

"""

import argparse
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Spacer, Table,
                                TableStyle, Paragraph, PageBreak)


def normalize_filename(text: str) -> str:
    out = text.replace(' ', '_').replace('/', '_').replace('\\', '_')
    out = ''.join(ch for ch in out if ch.isalnum() or ch in ('_', '-', '.'))
    return out[:120]


def generate_invoices(charge_df: pd.DataFrame, output_dir: str = 'invoices', issuer_name: str = 'Fly Kitchen'):
    if charge_df.empty:
        raise ValueError('charge_df is empty; no invoices to generate')

    required_cols = {'Lab', 'Container', 'Material', 'Special', 'Number', 'Price', 'Charges', 'Billing_period'}
    missing = required_cols - set(charge_df.columns)
    if missing:
        raise ValueError(f'Input DataFrame is missing required columns: {sorted(missing)}')

    # Determine the overall billing period range
    min_period = charge_df['Billing_period'].min()
    max_period = charge_df['Billing_period'].max()
    period_str = f"{min_period}-{max_period}" if min_period != max_period else str(min_period)

    output_path = Path(output_dir) / period_str
    output_path.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    style_h = styles['Heading1']
    style_n = styles['Normal']

    for lab, group in charge_df.groupby('Lab'):
        # Use the numeric min-max billing period to show a full span in the invoice header
        min_period = group['Billing_period'].min()
        max_period = group['Billing_period'].max()
        billing_period = f"{min_period}-{max_period}" if min_period != max_period else str(min_period)

        total_due = group['Charges'].sum()

        safe_lab = normalize_filename(str(lab)) or 'unknown_lab'
        safe_period = normalize_filename(billing_period)

        # Unique stable filename with period and generation timestamp
        timestamp = pd.Timestamp.utcnow().strftime('%Y%m%dT%H%M%SZ')
        filename = f'{safe_lab}_{safe_period}_{timestamp}.pdf'
        dest_file = output_path / filename

        doc = SimpleDocTemplate(str(dest_file), pagesize=letter,
                                leftMargin=0.75*inch, rightMargin=0.75*inch,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)

        story = []
        story.append(Paragraph(f'{issuer_name} Invoice', style_h))
        story.append(Spacer(1, 0.15*inch))

        story.append(Paragraph(f'<b>Customer:</b> {lab}', style_n))
        story.append(Paragraph(f'<b>Billing period:</b> {billing_period}', style_n))
        story.append(Spacer(1, 0.2*inch))

        data = [[
            'Month', 'Container', 'Material', 'Special', 'Count', 'Unit Price', 'Charges'
        ]]

        for _, row in group.sort_values(['Billing_period', 'Container', 'Material', 'Special']).iterrows():
            data.append([
                row['Billing_period'],
                row['Container'],
                row['Material'],
                row['Special'] if pd.notna(row['Special']) and str(row['Special']).strip() else '-',
                f"{row['Number']:.2f}",
                f"${row['Price']:.2f}",
                f"${row['Charges']:.2f}",
            ])

        # Use Paragraph for formatted text in table cells to avoid raw HTML tag output
        bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName='Helvetica-Bold')
        total_label = Paragraph('Total', bold_style)
        total_value = Paragraph(f'${total_due:.2f}', bold_style)

        data.append(['', total_label, '', '', '', '', total_value])

        table = Table(data, colWidths=[0.8*inch, 1.1*inch, 1.1*inch, 1.1*inch, 0.8*inch, 0.9*inch, 1.0*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f81bd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (2, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d9d9d9')),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, -1), (-1, -1), 6),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f2f2f2')),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.3*inch))

        story.append(Paragraph('Please contact jcfreeman2@wisc.edu with any questions.', style_n))

        doc.build(story)
        print(f'Generated invoice: {dest_file}')


def main():
    parser = argparse.ArgumentParser(description='Generate PDF invoices for each Lab from charge_df.')
    parser.add_argument('--input', required=True, help='Input CSV file containing charge_df')
    parser.add_argument('--output', default='invoices', help='Output folder for PDFs')
    parser.add_argument('--issuer', default='Fly Kitchen', help='Issuer name for invoice header')
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    # Convert columns to the right dtypes (help if they are strings)
    for c in ['Number', 'Price', 'Charges']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    if 'Billing_period' not in df.columns:
        df['Billing_period'] = pd.Timestamp.today().strftime('%Y-%m')

    generate_invoices(df, args.output, args.issuer)


if __name__ == '__main__':
    main()
