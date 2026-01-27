import sys
import os
import io

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.pdf_generator import generate_pdf_report

def main():
    print("Generating test PDF...")
    
    # Mock data
    role_name = "Product Manager"
    experience = "Middle"
    scores = {
        "hard_skills": 30,
        "soft_skills": 25,
        "thinking": 25,
        "mindset": 20
    }
    report_text = """
    # Impression
    Strong candidate with solid background.
    
    # Detailed Breakdown
    ## Hard Skills
    - Skill 1
    - Skill 2
    
    ## Soft Skills
    - Communication
    - Empathy
    
    # Recommendations
    1. Improve Python
    2. Learn SQL
    """
    conversation_history = []
    user_name = "Ivan Tester"
    
    # Raw averages for radar chart
    raw_averages = {
        "expertise": 8.5,
        "methodology": 7.0,
        "tools_proficiency": 6.5,
        "articulation": 9.0,
        "self_awareness": 8.0,
        "conflict_handling": 7.5,
        "depth": 6.0,
        "structure": 8.0,
        "systems_thinking": 7.0,
        "creativity": 6.5,
        "honesty": 9.5,
        "growth_orientation": 8.5
    }
    
    # PDP Data
    pdp_data = {
        "primary_goals": [
            {
                "metric_name": "System Design",
                "current_score": 6.0,
                "target_score": 8.5,
                "priority_reason": "Critical for Senior role"
            },
            {
                "metric_name": "Team Leadership",
                "current_score": 7.0,
                "target_score": 9.0,
                "priority_reason": "Required for promotion"
            }
        ],
        "timeline": "6 months",
        "plan_30_days": ["Do this", "Do that"],
        "plan_90_days": ["Then this"],
        "success_metrics": ["Metric 1"]
    }

    try:
        pdf_bytes = generate_pdf_report(
            role_name=role_name,
            experience=experience,
            scores=scores,
            report_text=report_text,
            conversation_history=conversation_history,
            user_name=user_name,
            raw_averages=raw_averages,
            pdp_data=pdp_data
        )
        
        output_path = os.path.abspath("test_report_fixed.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
            
        print(f"PDF successfully generated: {output_path}")
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
