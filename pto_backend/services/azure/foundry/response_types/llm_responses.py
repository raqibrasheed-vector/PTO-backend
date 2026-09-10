from typing import Dict, List, Any

from pydantic import BaseModel, Field


class InitialEligibility(BaseModel):
    months: int = Field(
        description="Number of months an employee must be employed before becoming eligible for PTO. This is important for deciding the vacation"
    )

    hours: int = Field(
        description="Minimum number of hours an employee must work before becoming eligible for PTO.If the employee does no meet the criteria, He is not eligible to earn vacation hours."
    )

    bonus: int = Field(
        description="Starting PTO bonus hours granted to the employee when they become eligible."
    )


class AccruingDefinition(BaseModel):
    type: str = Field(
        description="The employee time type that is allowed to accrue vacation, such as Regular."
    )

    period: int = Field(
        description="The continuity or employment period in months required for the applicable vacation accrual rule."
    )

    rate: str = Field(
        description="The vacation earning rate, including the number of vacation hours earned and the number of hours worked. Example: '8 vacation hours for every 400 hours'."
    )


class CarryOverDefinitions(BaseModel):
    max_hours: int = Field(
        description="Maximum number of vacation hours that can be carried over into the next period."
    )


class PTOEligibilityExtractor(BaseModel):
    Initial_Eligibility: InitialEligibility = Field(
        description="Initial PTO eligibility requirements, including eligible employment time, required working hours, and starting bonus. This is required to calculate further."
    )

    accuring_vacations: AccruingDefinition = Field(
        description="Rules defining which employee type can accrue vacation, the applicable continuity period, and the vacation earning rate."
    )

    carryovers: CarryOverDefinitions = Field(
        description="Rules defining the maximum vacation hours that may be carried over."
    )


class PTOHoursResponder(BaseModel):
    vacation_hours_available: int = Field(
        description="Extract total accured vacation hours. If the person does not meet initial Eligibility he is not authorized to take vacations, It will be 0 hours available."
    )


class PTOSummariser(BaseModel):
    vacation_hours_uncalculated: float = Field(
        description="Extract total vacation hours available before calculating the used used_vacations."
    )
    vacation_hours_available: float = Field(
        description="Extract total vacation hours available"
    )
    leaves_policy_breakdown: List[str] = Field(
        description="A short breakdown about the pto_extractor from the Vacation Policy include all the sections from Extracted Information output, like Initial Eligibility,Earning & accruing vacations,Carryovers and Termination & payouts"
    )
    leaves_accrued_calculation: List[str] = Field(
        description="A short description about the pto_calculator regarding the formula and how the leave calculated, make it step by step provess, as step1, step2 etc... And conver all the sections from Initial Eligibility,Earning & Accruing Vacations,Carryover these are the steps need to include."
    )
    leaves_available_calculation: str = Field(
        description='To get the available vacation hours, subtract used vacations from total accrued vacations. Example: To get the available vacation hours, subtract used vacations from total accrued vacations.  ["Calculation: 0 - 0.0 = 0.0, available vacation hours: 0.0"]'
    )
    leaves_policy: str = Field(
        description="Extract the content from the vacation_policy_unfiltered which has the information only regarding vacation policy. Extract the sentences having the word vacation or information in and around vacation policy. Make it descriptive and ensure all clause are included"
    )


class PTOSummariserParser(PTOSummariser):
    leaves_available_calculation_raw_json: Dict[str, Any]
