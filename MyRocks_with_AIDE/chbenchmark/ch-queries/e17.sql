explain
select    sum(ol_amount) / 2.0 as avg_yearly
from order_line, (select straight_join   i_id, avg(ol_quantity) as a
            from     order_line, item
            where    i_data_ra1 like 98
                 and ol_i_id = i_id
            group by i_id) t
where ol_i_id = t.i_id
    and ol_quantity < t.a LIMIT 10;
