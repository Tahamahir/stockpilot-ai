select
    supplier_performance_key,
    tenant_id,
    supplier_id,
    supplier_name,
    supplier_score

from {{ ref('mart_supplier_performance') }}

where supplier_score < 0
   or supplier_score > 100