"""
Generate an academic-style PDF report for the Factor Crowding Risk project.
Uses reportlab for PDF generation with embedded figures and formatted tables.

Writing style: Neutral, objective, evidence-based. No exaggerated claims.
"""

import os
import sys
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, ListFlowable, ListItem, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

# ============================================================================
# CONFIGURATION
# ============================================================================

OUTPUT_PDF = os.path.join("outputs", "factor_crowding_risk_project_report.pdf")
OUTPUT_DIR = "outputs"

IMAGES = {
    "crowding_signal": os.path.join(OUTPUT_DIR, "visualization_1_crowding_signal_over_time.png"),
    "cumulative_returns": os.path.join(OUTPUT_DIR, "visualization_2_cumulative_returns_comparison.png"),
    "drawdown": os.path.join(OUTPUT_DIR, "visualization_3_drawdown_comparison.png"),
    "scatter": os.path.join(OUTPUT_DIR, "visualization_4_crowding_vs_forward_return.png"),
}

METRICS_CSV = os.path.join(OUTPUT_DIR, "metrics_table.csv")

# ============================================================================
# PDF GENERATION
# ============================================================================

def generate_pdf():
    """Generate the complete PDF report."""
    
    print("="*80)
    print("PDF PAPER GENERATOR")
    print("="*80)
    print(f"Output: {OUTPUT_PDF}")
    print("="*80)
    
    doc = SimpleDocTemplate(
        OUTPUT_PDF,
        pagesize=LETTER,
        leftMargin=0.9*inch,
        rightMargin=0.9*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom paragraph styles — Times font
    title_style = ParagraphStyle(
        'Title', parent=styles['Title'],
        fontName='Times-Bold', fontSize=18,
        alignment=TA_CENTER, spaceAfter=12
    )
    
    author_style = ParagraphStyle(
        'Author', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=12,
        alignment=TA_CENTER, spaceAfter=4
    )
    
    affiliation_style = ParagraphStyle(
        'Affiliation', parent=styles['Normal'],
        fontName='Times-Italic', fontSize=11,
        alignment=TA_CENTER, spaceAfter=16
    )
    
    date_style = ParagraphStyle(
        'Date', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=11,
        alignment=TA_CENTER, spaceAfter=20
    )
    
    disclaimer_style = ParagraphStyle(
        'Disclaimer', parent=styles['Normal'],
        fontName='Times-Italic', fontSize=9,
        alignment=TA_CENTER, spaceAfter=12,
        textColor=colors.grey
    )
    
    heading_style = ParagraphStyle(
        'Heading', parent=styles['Heading2'],
        fontName='Times-Bold', fontSize=14,
        spaceAfter=8, spaceBefore=14
    )
    
    subheading_style = ParagraphStyle(
        'Subheading', parent=styles['Heading3'],
        fontName='Times-Bold', fontSize=12,
        spaceAfter=4, spaceBefore=8
    )
    
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=10.5,
        alignment=TA_JUSTIFY, spaceAfter=6
    )
    
    body_indent_style = ParagraphStyle(
        'BodyIndent', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=10.5,
        alignment=TA_JUSTIFY, spaceAfter=4,
        leftIndent=0.2*inch
    )
    
    caption_style = ParagraphStyle(
        'Caption', parent=styles['Normal'],
        fontName='Times-Italic', fontSize=9.5,
        alignment=TA_LEFT, spaceAfter=10
    )
    
    abstract_style = ParagraphStyle(
        'Abstract', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=10.5,
        alignment=TA_JUSTIFY, spaceAfter=12,
        leftIndent=0.5*inch, rightIndent=0.5*inch
    )
    
    ref_style = ParagraphStyle(
        'Reference', parent=styles['Normal'],
        fontName='Times-Roman', fontSize=9.5,
        alignment=TA_LEFT, spaceAfter=3,
        leftIndent=0.3*inch, firstLineIndent=-0.3*inch
    )
    
    story = []
    
    # ========================================================================
    # TITLE PAGE
    # ========================================================================
    
    story.append(Spacer(1, 1*inch))
    story.append(Paragraph("Factor Crowding Risk and Alpha Decay Modeling", title_style))
    story.append(Paragraph("A Data Science Project on U.S. Equities", title_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Ken Ira Lacson", author_style))
    story.append(Paragraph("Portfolio Project — Quantitative Finance and Machine Learning", affiliation_style))
    story.append(Paragraph(datetime.now().strftime('%B %d, %Y'), date_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "This is a project report for educational and portfolio demonstration purposes. "
        "It is not investment advice and does not claim to generate alpha or beat the market.",
        disclaimer_style
    ))
    
    # ========================================================================
    # ABSTRACT
    # ========================================================================
    
    story.append(PageBreak())
    story.append(Paragraph("Abstract", heading_style))
    story.append(Spacer(1, 0.05*inch))
    
    abstract_text = (
        "This project examines whether observable crowding metrics can predict "
        "changes in factor performance in U.S. equities. Using S&P 500 data "
        "from 2019 to 2024, we constructed crowding proxies for Value and "
        "Momentum factors and evaluated their relationship to forward factor "
        "returns. A staged modeling approach was used, starting with baseline "
        "models before testing more complex techniques. The Value factor showed "
        "the strongest predictive signal in this sample, with a logistic "
        "regression F1 score of 0.9483 when predicting 3-month forward returns. "
        "A trading strategy using continuous position sizing based on linear "
        "regression predictions showed a Sharpe ratio improvement of +0.0486 "
        "and a max drawdown reduction of 4.16% compared to a static allocation "
        "in the backtest. The Momentum factor exhibited a weaker signal, with "
        "best F1 of 0.6593. This report documents the methodology, results, "
        "and limitations of the work."
    )
    story.append(Paragraph(abstract_text, abstract_style))
    
    # ========================================================================
    # 1. INTRODUCTION
    # ========================================================================
    
    story.append(PageBreak())
    story.append(Paragraph("1. Introduction", heading_style))
    
    intro_paragraphs = [
        "Quantitative investment strategies often use systematic factors such as "
        "value, momentum, or low volatility. One challenge in systematic investing "
        "is factor crowding: as more capital flows into a strategy, the predictive "
        "power of the signal may decrease. This phenomenon is sometimes referred "
        "to as alpha decay.",
        
        "The August 2007 quant crisis is a frequently cited example where multiple "
        "quantitative strategies experienced simultaneous losses. This event "
        "highlighted the potential value of risk management tools that might "
        "detect crowding before it leads to drawdowns.",
        
        "This project explores whether crowding can be measured using publicly "
        "available data and whether such measurements could inform portfolio "
        "allocation decisions. The work is framed as a practical investigation "
        "rather than a formal research study. The goal is not to discover new "
        "alpha but to evaluate whether simple, interpretable crowding signals "
        "show any relationship to factor performance.",
        
        "The research question is: Can a cross-sectional crowding score for "
        "standard equity factors predict the future decay of that factor's "
        "information coefficient? Specifically, do anomalous patterns of high "
        "correlation and concentrated exposure within a factor's top-quintile "
        "stocks precede a decline in forward factor performance?"
    ]
    
    for para in intro_paragraphs:
        story.append(Paragraph(para, body_style))
    
    # ========================================================================
    # 2. METHODOLOGY
    # ========================================================================
    
    story.append(Paragraph("2. Methodology", heading_style))
    
    story.append(Paragraph(
        "The methodology follows a staged approach, beginning with simple "
        "baseline models before introducing more complex techniques. This "
        "approach was chosen to maintain interpretability and to assess "
        "whether additional complexity provides any benefit.",
        body_style
    ))
    
    # 2.1 Data
    story.append(Paragraph("2.1 Data", subheading_style))
    
    story.append(Paragraph(
        "The analysis uses daily adjusted close prices for S&P 500 constituents "
        "from January 2018 to December 2024. Data was obtained through the "
        "yfinance library. The initial universe consisted of 503 stocks, with "
        "final usable data for 498 stocks after accounting for delistings and "
        "IPOs. Weekly rebalancing was used, yielding 304 observations from "
        "March 2019 to December 2024.",
        body_style
    ))
    
    story.append(Paragraph(
        "Factor returns were constructed for two factors: Momentum (12-1 month) "
        "and Value (Book-to-Market proxy using inverse momentum). Both factors "
        "were constructed as long-short portfolios: long the top quintile and "
        "short the bottom quintile, rebalanced monthly.",
        body_style
    ))
    
    # 2.2 Features
    story.append(Paragraph("2.2 Features", subheading_style))
    
    story.append(Paragraph(
        "Three crowding proxies were implemented using available data:",
        body_style
    ))
    
    feature_list = ListFlowable([
        ListItem(Paragraph("<b>Pairwise Correlation:</b> Average correlation of daily returns among stocks in the factor's top quintile over a 60-day rolling window.", body_style)),
        ListItem(Paragraph("<b>Herfindahl-Hirschman Index (HHI):</b> Measure of factor exposure concentration across the universe.", body_style)),
        ListItem(Paragraph("<b>Valuation Spread:</b> Price spread between top and bottom quintiles as a proxy for valuation dispersion.", body_style)),
    ], bulletType='bullet')
    story.append(feature_list)
    
    story.append(Paragraph(
        "Additional transformed features were generated from these, including "
        "squared terms, rolling percentiles, deltas, standard deviations, "
        "log transforms, and z-scores. A composite z-score was also computed.",
        body_style
    ))
    
    # 2.3 Modeling Approach
    story.append(Paragraph("2.3 Modeling Approach", subheading_style))
    
    story.append(Paragraph(
        "A staged modeling strategy was used. Baseline models included "
        "logistic regression (predicting negative forward returns) and "
        "linear regression (predicting forward IC). Key experiments included:",
        body_style
    ))
    
    modeling_list = ListFlowable([
        ListItem(Paragraph("<b>Feature Transform Experiment:</b> 13 transformed features were tested individually to identify which forms of the crowding proxies carried the strongest signal.", body_style)),
        ListItem(Paragraph("<b>Target Definition Experiment:</b> Nine different target definitions were tested, including forward returns at various horizons, Spearman rank IC, and rolling average IC.", body_style)),
        ListItem(Paragraph("<b>Trading Strategy Backtests:</b> Binary threshold rules and continuous sizing strategies were evaluated. Continuous sizing uses linear regression to predict forward returns, then scales position sizes based on the predicted return.", body_style)),
    ], bulletType='bullet')
    story.append(modeling_list)
    
    # 2.4 Evaluation Framework
    story.append(Paragraph("2.4 Evaluation Framework", subheading_style))
    
    story.append(Paragraph(
        "The project was evaluated using classification F1 score, regression R², "
        "Sharpe ratio, max drawdown, and annualized volatility. The backtest was "
        "used to translate the crowding signal into portfolio management terms.",
        body_style
    ))
    
    # ========================================================================
    # 3. RESULTS
    # ========================================================================
    
    story.append(PageBreak())
    story.append(Paragraph("3. Results", heading_style))
    
    story.append(Paragraph(
        "The results are organized by the staged experiments.",
        body_style
    ))
    
    # 3.1 Feature Transform Experiment
    story.append(Paragraph("3.1 Feature Transform Experiment", subheading_style))
    
    story.append(Paragraph(
        "For the Value factor, the raw correlation feature (correlation_raw) "
        "achieved the highest F1 score of 0.8155 in this sample. No transformed "
        "feature improved upon this baseline. For the Momentum factor, the HHI_z "
        "transform achieved the highest F1 score of 0.6061.",
        body_style
    ))
    
    # Table: Best Features
    data_best_features = [
        ["Factor", "Best Feature", "F1", "R²", "Change from Baseline"],
        ["Value", "correlation_raw", "0.8155", "-0.1712", "None"],
        ["Momentum", "hhi_z", "0.6061", "-0.8807", "+0.4061"],
    ]
    table_best_features = Table(data_best_features, colWidths=[1.2*inch, 1.6*inch, 0.8*inch, 0.9*inch, 1.8*inch])
    table_best_features.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(Spacer(1, 0.1*inch))
    story.append(table_best_features)
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<i>Table 2: Best features by factor from Feature Transform Experiment.</i>",
        caption_style
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # Table: Feature Sets
    data_feature_sets = [
        ["Feature Set", "Momentum F1", "Value F1", "Momentum R²", "Value R²"],
        ["Correlation", "0.000", "0.819", "-0.154", "-0.136"],
        ["Z-Composite", "0.516", "0.761", "-0.687", "-0.431"],
        ["All Features", "0.516", "0.761", "-0.154", "-0.136"],
        ["Valuation Spread", "0.488", "0.647", "-0.655", "-0.646"],
        ["HHI", "0.000", "0.819", "-1.036", "-0.977"],
    ]
    table_feature_sets = Table(data_feature_sets, colWidths=[1.3*inch, 1.2*inch, 1.0*inch, 1.2*inch, 1.0*inch])
    table_feature_sets.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(table_feature_sets)
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<i>Table 3: Different feature sets tested. Correlation alone worked best for Value (F1: 0.819) in this sample.</i>",
        caption_style
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # Table: Window Lengths
    data_windows = [
        ["Window", "Momentum F1", "Value F1", "Momentum R²", "Value R²"],
        ["30 days", "0.459", "0.747", "-0.798", "-0.424"],
        ["60 days", "0.516", "0.761", "-0.687", "-0.431"],
        ["90 days", "0.556", "0.758", "-0.537", "-0.388"],
    ]
    table_windows = Table(data_windows, colWidths=[1.0*inch, 1.2*inch, 1.0*inch, 1.2*inch, 1.0*inch])
    table_windows.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(table_windows)
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<i>Table 4: Different window lengths tested. 90-day window showed slightly higher F1 for Momentum (0.556) in this sample.</i>",
        caption_style
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # 3.2 Target Definition Experiment
    story.append(Paragraph("3.2 Target Definition Experiment", subheading_style))
    
    story.append(Paragraph(
        "The Value factor performed best with a 3-month forward return "
        "target, achieving an F1 score of 0.9483 in this sample.",
        body_style
    ))
    
    story.append(Paragraph(
        "The Momentum factor performed best with a Spearman 6-week target, "
        "achieving an F1 score of 0.6593.",
        body_style
    ))
    
    # Table: Best Targets
    data_best_targets = [
        ["Factor", "Best Target", "Feature", "F1", "R²"],
        ["Value", "forward_3m", "correlation_raw", "0.9483", "-0.9876"],
        ["Momentum", "spearman_6w", "hhi_z", "0.6593", "-0.0076"],
    ]
    table_best_targets = Table(data_best_targets, colWidths=[1.2*inch, 1.5*inch, 1.6*inch, 0.9*inch, 1.0*inch])
    table_best_targets.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(Spacer(1, 0.1*inch))
    story.append(table_best_targets)
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<i>Table 5: Best targets by factor from Target Definition Experiment.</i>",
        caption_style
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # 3.3 Trading Strategy Backtest
    story.append(Paragraph("3.3 Trading Strategy Backtest", subheading_style))
    
    story.append(Paragraph(
        "Binary threshold rules (reducing exposure when crowding exceeds a "
        "percentile threshold) showed negative Sharpe improvement for both "
        "factors in this sample. The best binary configuration showed a "
        "Sharpe change of -0.0138 for Value and -0.0080 for Momentum.",
        body_style
    ))
    
    story.append(Paragraph(
        "Continuous position sizing using linear regression predictions "
        "showed different results. The Value strategy showed a Sharpe ratio "
        "improvement of +0.0486 and a max drawdown reduction of 4.16% "
        "compared to the static allocation in the backtest. Total return "
        "improved by 3.43% and volatility decreased by 1.03% in this sample.",
        body_style
    ))
    
    # Table: Binary Results
    data_binary = [
        ["Factor", "Best Threshold", "Best Reduction", "Sharpe Δ", "Drawdown Δ"],
        ["Value", "75th", "10%", "-0.0138", "-0.57%"],
        ["Momentum", "75th", "10%", "-0.0080", "-0.88%"],
    ]
    table_binary = Table(data_binary, colWidths=[1.2*inch, 1.3*inch, 1.3*inch, 1.2*inch, 1.2*inch])
    table_binary.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(Spacer(1, 0.1*inch))
    story.append(table_binary)
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<i>Table 6: Binary threshold strategy results. Both factors showed negative Sharpe improvement in this sample.</i>",
        caption_style
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # Table: Continuous Results
    data_continuous = [
        ["Test", "Factor", "Sharpe Δ", "Drawdown Δ"],
        ["Continuous Sizing", "Value", "+0.0441", "-3.08%"],
        ["Decision Tree (Depth 3)", "Value", "+0.0286", "-"],
        ["Decision Tree (Depth 2)", "Value", "+0.0192", "-"],
        ["Decision Tree (Depth 3)", "Momentum", "+0.0043", "-"],
    ]
    table_continuous = Table(data_continuous, colWidths=[2.0*inch, 1.5*inch, 1.3*inch, 1.3*inch])
    table_continuous.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(Spacer(1, 0.1*inch))
    story.append(table_continuous)
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "<i>Table 7: Continuous sizing and decision tree results. Continuous sizing showed the largest Sharpe improvement in this sample.</i>",
        caption_style
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # 3.4 Summary Metrics
    story.append(Paragraph("3.4 Summary Metrics", subheading_style))
    
    story.append(Paragraph(
        "Table 1 shows the performance metrics for the Value factor strategy "
        "using continuous position sizing.",
        body_style
    ))
    
    if os.path.exists(METRICS_CSV):
        try:
            df = pd.read_csv(METRICS_CSV)
            table_data = [df.columns.tolist()] + df.values.tolist()
            col_widths = [1.4*inch, 1.4*inch, 1.6*inch, 1.2*inch]
            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('FONTNAME', (0, 0), (0, -1), 'Times-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(Spacer(1, 0.1*inch))
            story.append(table)
            story.append(Spacer(1, 0.05*inch))
            story.append(Paragraph(
                "<i>Table 1: Performance metrics for Value strategy with continuous sizing.</i>",
                caption_style
            ))
        except Exception as e:
            print(f"  Warning: Could not load metrics table: {e}")
    
    # ========================================================================
    # 4. FIGURES
    # ========================================================================
    
    story.append(PageBreak())
    story.append(Paragraph("4. Figures", heading_style))
    
    story.append(Paragraph(
        "The following figures illustrate the analysis.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # Figure 1
    if os.path.exists(IMAGES["crowding_signal"]):
        try:
            img = Image(IMAGES["crowding_signal"], width=6.5*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 0.05*inch))
            story.append(Paragraph(
                "<b>Figure 1:</b> Value factor crowding signal over time (2019-2024). "
                "The red dashed line indicates the 75th percentile threshold. "
                "Shaded regions indicate periods identified as crowded.",
                caption_style
            ))
            story.append(Spacer(1, 0.15*inch))
        except Exception as e:
            print(f"  Warning: Could not load crowding_signal image: {e}")
    
    # Figure 2
    if os.path.exists(IMAGES["cumulative_returns"]):
        try:
            img = Image(IMAGES["cumulative_returns"], width=6.5*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 0.05*inch))
            story.append(Paragraph(
                "<b>Figure 2:</b> Cumulative returns comparison between static and "
                "crowding-aware strategies. Total return changed from -10.46% "
                "to -7.02% in this sample.",
                caption_style
            ))
            story.append(Spacer(1, 0.15*inch))
        except Exception as e:
            print(f"  Warning: Could not load cumulative_returns image: {e}")
    
    # Figure 3
    if os.path.exists(IMAGES["drawdown"]):
        try:
            img = Image(IMAGES["drawdown"], width=6.5*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 0.05*inch))
            story.append(Paragraph(
                "<b>Figure 3:</b> Drawdown comparison between static and crowding-aware "
                "strategies. Maximum drawdown was -26.88% for static and "
                "-22.72% for crowding-aware in this sample.",
                caption_style
            ))
            story.append(Spacer(1, 0.15*inch))
        except Exception as e:
            print(f"  Warning: Could not load drawdown image: {e}")
    
    # Figure 4
    if os.path.exists(IMAGES["scatter"]):
        try:
            img = Image(IMAGES["scatter"], width=6.5*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 0.05*inch))
            story.append(Paragraph(
                "<b>Figure 4:</b> Crowding signal vs forward 3-month return. "
                "The regression line shows a positive relationship in this "
                "sample (correlation: 0.2811, R²: 0.079).",
                caption_style
            ))
            story.append(Spacer(1, 0.15*inch))
        except Exception as e:
            print(f"  Warning: Could not load scatter image: {e}")
    
    # ========================================================================
    # 5. DISCUSSION
    # ========================================================================
    
    story.append(PageBreak())
    story.append(Paragraph("5. Discussion", heading_style))
    
    discussion_paragraphs = [
        "The results suggest that crowding signals for the Value factor may "
        "be measurable using publicly available data. The continuous sizing "
        "approach showed some improvement in risk-adjusted returns in this "
        "sample, though the magnitude of the improvement is modest.",
        
        "Binary threshold rules did not perform as well as continuous sizing "
        "in this sample. This may suggest that crowding is not a binary "
        "state but exists on a continuum.",
        
        "The Momentum factor showed a weaker signal in this analysis. "
        "The positive R² (0.0186) for Momentum regression is a small "
        "improvement over the negative values observed in initial experiments, "
        "though the magnitude is modest.",
        
        "The backtest assumes frictionless trading and does not model "
        "transaction costs, market impact, or short-selling constraints. "
        "The analysis only considered two factors and the S&P 500 universe. "
        "The results may not generalize to other factors or markets."
    ]
    
    for para in discussion_paragraphs:
        story.append(Paragraph(para, body_style))
    
    # ========================================================================
    # 6. LIMITATIONS
    # ========================================================================
    
    story.append(Paragraph("6. Limitations", heading_style))
    
    limitations_list = ListFlowable([
        ListItem(Paragraph("<b>Data Constraints:</b> The analysis uses publicly available data and does not incorporate proprietary flow data. 13F institutional ownership data was not implemented.", body_style)),
        ListItem(Paragraph("<b>Factor Scope:</b> Only two factors (Value and Momentum) were analyzed. The results may not extend to other factors.", body_style)),
        ListItem(Paragraph("<b>Market Universe:</b> The analysis is limited to S&P 500 stocks. Crowding dynamics may differ in other markets.", body_style)),
        ListItem(Paragraph("<b>Time Period:</b> The 5-year window (2019-2024) may not capture multi-cycle behavior.", body_style)),
        ListItem(Paragraph("<b>Macroeconomic Controls:</b> The model does not condition on macroeconomic regimes.", body_style)),
        ListItem(Paragraph("<b>Simplified Backtest:</b> Transaction costs, market impact, and short-selling constraints were not modeled.", body_style)),
        ListItem(Paragraph("<b>Attribution Not Causation:</b> The analysis identifies statistical associations but does not establish causal relationships.", body_style)),
    ], bulletType='bullet')
    story.append(limitations_list)
    
    # ========================================================================
    # 7. CONCLUSION
    # ========================================================================
    
    story.append(Paragraph("7. Conclusion", heading_style))
    
    conclusion_paragraphs = [
        "This project examined whether crowding metrics can predict "
        "factor performance changes and inform portfolio allocation decisions. "
        "Using S&P 500 data from 2019 to 2024, we found some evidence that "
        "crowding signals for the Value factor may be measurable and could "
        "potentially improve risk-adjusted returns through continuous position "
        "sizing.",
        
        "The strategy using continuous sizing showed a Sharpe ratio improvement "
        "of +0.0486 and a max drawdown reduction of 4.16% in this sample. "
        "The Momentum factor showed a weaker signal, with best F1 of 0.6593. "
        "The analysis used a staged, baseline-first approach that prioritized "
        "interpretability.",
        
        "The work demonstrates a practical approach to examining crowding "
        "risk. The results are specific to the sample and period analyzed. "
        "Future work could incorporate additional factors, extend the universe, "
        "or test more sophisticated position sizing methods."
    ]
    
    for para in conclusion_paragraphs:
        story.append(Paragraph(para, body_style))
    
    # ========================================================================
    # 8. REFERENCES
    # ========================================================================
    
    story.append(PageBreak())
    story.append(Paragraph("References", heading_style))
    
    references = [
        "Arnott, R., Kalesnik, V., & Wu, L. (2019). The incredible shrinking factor return. <i>Journal of Portfolio Management</i>.",
        "Cahan, R., & Luo, Y. (2013). Standing out from the crowd: Measuring crowding in quantitative strategies. <i>Journal of Portfolio Management</i>.",
        "Fama, E. F., & French, K. R. (1993). Common risk factors in the returns on stocks and bonds. <i>Journal of Financial Economics</i>, 33(1), 3-56.",
        "Khandani, A. E., & Lo, A. W. (2007). What happened to the quants in August 2007? <i>Journal of Investment Management</i>, 5(4), 5-26."
    ]
    
    for ref in references:
        story.append(Paragraph(ref, ref_style))
    
    # ========================================================================
    # BUILD
    # ========================================================================
    
    print("\nBuilding PDF document...")
    doc.build(story)
    print(f"\n✅ PDF generated: {OUTPUT_PDF}")
    
    return OUTPUT_PDF


if __name__ == "__main__":
    generate_pdf()