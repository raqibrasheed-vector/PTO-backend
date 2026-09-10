from datetime import date, timedelta
from typing import Any

from pto_backend.services.azure.cosmosdb.schema import FiltersType
from pto_backend.types.api_types import ModelsPagination


class DatabaseQueryUtils:
    """Database query utils"""

    @staticmethod
    def _exclusive_end_date(end_date: str | None) -> str | None:
        """Make a date-only end filter inclusive of the selected day."""
        if not end_date or len(end_date) != 10:
            return end_date

        try:
            return (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
        except ValueError:
            return end_date

    async def generate_distinct_query(self, fields: list[str]) -> str:
        if not fields:
            raise ValueError("At least one field is required")

        select_fields = ", ".join(f"c.{field}" for field in fields)

        return f"SELECT DISTINCT {select_fields} FROM c"

    async def get_pto_logging_data(
        self,
        limit: int,
        offset: int,
        start_date: str | None = None,
        end_date: str | None = None,
        filters: list[FiltersType] | None = None,
        feedback_logging_ids: list[str] | None = None,
    ) -> tuple[str, list[Any]]:

        pto_query = """
            SELECT
                c.id,
                c.employee_id,
                c.start_date,
                c.end_date,
                c.employee_name,
                c.client_name,
                c.total_hours,
                c.total_leaves_used,
                c.state,
                c.leaves_available,
                c.user_name,
                c.file_name,
                c.created_at
            FROM c
        """

        parameters = []
        where_conditions = []

        # Date filters
        if start_date and end_date:
            end_date = self._exclusive_end_date(end_date)
            if start_date == end_date:
                where_conditions.append("STARTSWITH(c.created_at, @start_date)")
                parameters.append(
                    {
                        "name": "@start_date",
                        "value": start_date,
                    }
                )
            else:
                where_conditions.append(
                    "c.created_at >= @start_date AND c.created_at < @end_date"
                )
                parameters.extend(
                    [
                        {
                            "name": "@start_date",
                            "value": start_date,
                        },
                        {
                            "name": "@end_date",
                            "value": end_date,
                        },
                    ]
                )

        # Allowed fields for sorting
        allowed_sort_fields = {
            "id": "c.id",
            "employee_id": "c.employee_id",
            "start_date": "c.start_date",
            "end_date": "c.end_date",
            "employee_name": "c.employee_name",
            "client_name": "c.client_name",
            "total_hours": "c.total_hours",
            "total_leaves_used": "c.total_leaves_used",
            "state": "c.state",
            "leaves_available": "c.leaves_available",
            "user_name": "c.user_name",
            "file_name": "c.file_name",
            "created_at": "c.created_at",
        }

        sort_field = "c.start_date"
        sort_direction = "ASC"

        if filters:
            for index, filter_item in enumerate(filters):
                field = allowed_sort_fields.get(filter_item.key)

                # Ignore unsupported fields
                if not field:
                    continue

                if filter_item.isSort:
                    # key = column name
                    # value = ASC / DESC

                    direction = filter_item.value.upper()

                    if direction in ("ASC", "DESC"):
                        sort_field = field
                        sort_direction = direction

                else:
                    # key = column name
                    # value = value to filter

                    parameter_name = f"@filter_{index}"

                    where_conditions.append(f"{field} = {parameter_name}")

                    parameters.append(
                        {
                            "name": parameter_name,
                            "value": filter_item.value,
                        }
                    )

        if feedback_logging_ids is not None:
            where_conditions.append("ARRAY_CONTAINS(@feedback_ids, c.id)")
            parameters.append(
                {
                    "name": "@feedback_ids",
                    "value": feedback_logging_ids,
                }
            )

        # Add WHERE clause
        if where_conditions:
            pto_query += " WHERE " + " AND ".join(where_conditions)

        # Add ORDER BY
        if sort_field:
            pto_query += f" ORDER BY {sort_field} {sort_direction}"

        # Pagination
        pto_query += """
            OFFSET @offset LIMIT @limit
        """

        parameters.extend(
            [
                {
                    "name": "@offset",
                    "value": offset,
                },
                {
                    "name": "@limit",
                    "value": limit,
                },
            ]
        )

        return pto_query, parameters

    async def get_pto_logging_count(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        filters: list[FiltersType] | None = None,
        feedback_logging_ids: list[str] | None = None,
    ) -> tuple[str, list[Any]]:
        """Build a count query using exactly the same filters as the data query."""
        query, parameters = await self.get_pto_logging_data(
            start_date=start_date,
            end_date=end_date,
            limit=1,
            offset=0,
            filters=filters,
            feedback_logging_ids=feedback_logging_ids,
        )

        query_without_pagination = query.split(" OFFSET ", 1)[0]
        query_without_order = query_without_pagination.split(" ORDER BY ", 1)[0]
        where_clause = query_without_order.split(" FROM c", 1)[1]

        count_parameters = [
            parameter
            for parameter in parameters
            if parameter["name"] not in {"@offset", "@limit"}
        ]

        return f"SELECT VALUE COUNT(1) FROM c{where_clause}", count_parameters

    async def get_pto_feedback_data(self) -> str:

        feedback_query = """
            SELECT
                c.pto_logging_id,
                c.feedback,
                c.feedback_type
            FROM c
            WHERE ARRAY_CONTAINS(@ids, c.pto_logging_id)
        """

        return feedback_query

    async def get_paginations(
        self,
        total_count: int,
        page_size: int,
        page_index: int,
    ) -> ModelsPagination:

        total_pages = (total_count + page_size - 1) // page_size

        page = max(1, min(page_index, total_pages if total_pages > 0 else 1))

        start = (page - 1) * page_size

        end = min(start + page_size, total_count)

        return ModelsPagination(
            total_pages=total_pages,
            total_records=total_count,
            page=page,
            start=start,
            end=end,
        )
