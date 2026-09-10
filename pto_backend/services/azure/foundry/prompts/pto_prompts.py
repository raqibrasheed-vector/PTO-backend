prompt_pto_extractor = """
Task: Extract the following pieces of information from a PTO vacation policy: 1. Initial Eligibility, 2. Earning & accruing vacations, 3. Carryovers, and 4. Termination & payouts. \n
Instructions:
-Do not infer dates or earning rate or any other details from the examples provided. The examples are strictly for reference.
- Do not generate or infer any information that is not explicitly present in the provided text. Only restructure and clean the given content.

Example:
Vacation Policy:  You are not eligible to earn or accrue any vacation until you have completed 200 regular hours of service within six months at the initial commencement of employment on this Assignment. After this initial period of employment, ACTALENT agrees that you have earned or are eligible to earn 8 vacation hours, for every 200 Regular hours (not including overtime) of compensated service in a continuous six (6) month period. Accrued but unused vacation hours may be carried over into the next calendar year, however the maximum amount of accrued vacation may not exceed one hundred and sixty (160) hours at any given time. Unless state or applicable law requires otherwise, unused accrued vacation will not be paid out upon termination and vacation will not accrue on a pro-rata basis.

Extracted Information:
Initial Eligibility: You are not eligible to earn or accrue any vacation until you have completed 200 regular hours of service within six months at the initial commencement of employment on this Assignment.
Earning & accruing vacations: After this initial period of employment, ACTALENT agrees that you have earned or are eligible to earn 8 vacation hours, for every 200 Regular hours (not including overtime) of compensated service in a continuous six (6) month period.
Carryovers: Accrued but unused vacation hours may be carried over into the next calendar year, however the maximum amount of accrued vacation may not exceed one hundred and sixty (160) hours at any given time.
Termination & payouts: Unless state or applicable law requires otherwise, unused accrued vacation will not be paid out upon termination and vacation will not accrue on a pro-rata basis.

Input:

{pto_document_context}

Output:

Initial Eligibility:
Earning & accruing vacations:
Carryovers:
Termination & payouts:
"""

prompt_pto_cail = """
Based on Example below , calculate vacation hours of the Input. Let's think step-by-step
**Instructions:**
- Do not infer any missing details such as accrual rates, dates, or additional policies. Only use the explicitly provided information.
- If an accrual rate is missing, do not assume it from anywhere.
- Do not generate or assume any data that is not explicitly mentioned.
-Do not infer dates or earning rate or any other details from the examples provided. The examples are strictly for reference.

Step-by-Step process

1. **Initial Eligibility**: You need to complete 400 regular hours of service within six months to start earning vacation hours. If You have worked for 8 months and 1000 hours,you have met this initial requirement.


2. **Earning & Accruing Vacations**:

    - Total hours worked: 784
    - Earning Rate : 8 vacation hours for every 400
    - Vacation Earned for 1 hour : 8/400
    - Vacation Earned for 784 hours : 784 * Vacation Earned for 1 hour 
    So, You have accrued 15.68 vacation hours.Yes, the vacation eligibility is met, If not you have 0 accrued vacation hours.

*Above example is strictly for reference do not assume any dates or earning rate from above example, if no earning rate is present  don't calculate further*
Input:

Task : Calculate PTO/Vacation accruals based on hire date {start_date} and today's date for {end_date}. YTD Regular Hours worked {regular_hours_worked}.
"""

prompt_pto_non_cail = """
Based on Example below , calculate vacation hours of the Input. Lets think step-by-step
**Instructions:**
- Do not infer any missing details such as accrual rates, dates, or additional policies. Only use the explicitly provided information.
- If an accrual rate is missing, do not assume it from anywhere.
- Do not generate or assume any data that is not explicitly mentioned.
-Do not infer dates or earning rate or any other details from the examples provided. The examples are strictly for reference.

Step-by-Step process

1. **Initial Eligibility**: You need to complete 400 regular hours of service within six months to start earning vacation hours. If You have worked for 8 months and 1000 hours, you have met this initial requirement.

2. **Earning & Accruing Vacations**: 

    - Total hours worked: 784
    - Earning Rate : 8 vacation hours for every 400
    - Z =  784/400
    - Y =  Round Z down to the nearest multiple of the significance 1
    - X = Y * 8 (8 is the earning rate for every 400 hours)
    So, you have earned 8 vacation hours for the 784 hours worked after the initial 400 hours.

**Conclusion**: Yes, the vacation eligibility is met, and you have accrued 8 vacation hours. If not you have 0 accrued vacation hours.

*Above example is strictly for reference do not assume any dates or earning rate from above example, if no earning rate is present don't calculate further*
Input:

Task : Calculate PTO/Vacation accruals based on hire date {start_date} and today's date for {end_date}. YTD Regular Hours worked {regular_hours_worked}.
"""

prompt_pto_summarizer = """
Input:Calculate available vacation for an employee by subtracting used vacation hours from total vacation hours using the following steps:
**Instructions:**
- Do not generate or assume any data that is not explicitly mentioned.
- Do not infer dates or earning rate or any other details from the examples provided. The examples are strictly for reference.

T = Extract total accured vacation hours from pto_calculator.
Z = Subtract {used_vacations} from T.

For reference here are the examples (Note: Do not refer this data for acutal calculations)
Example1: If total accrued vacation hours are 16. That is if T is equal to 16.
To get the available vacation hours, subtract used vacations from total accrued vacations, that is T. If used vacation hours are 16. Available vacation hours are- Z = T - 16.
Here in this case Z = 16 - 16. Which is equal to 0. So Z = 0.

Conclusion of example 1:  
"Calculation": "16 - 16 = 0",
"available vacation hours": 0
"""
