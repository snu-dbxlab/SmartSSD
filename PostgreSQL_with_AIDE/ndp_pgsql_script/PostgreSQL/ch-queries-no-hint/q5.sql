select     n_name,
     sum(ol_amount) as revenue
from     customer, orders, order_line, stock, supplier, nation, region
where    c_w_id = o_w_id
     and c_d_id = o_d_id
     and c_id = o_c_id
     and ol_o_id = o_id
     and ol_w_id = o_w_id
     and ol_d_id=o_d_id
     and ol_w_id = s_w_id
     and ol_i_id = s_i_id
--     and mod((s_w_id * s_i_id),10000) = su_suppkey
     and s_i_id = su_suppkey
--     and ascii(substr(c_state,1,1)) = su_nationkey
     and c_state_a = su_nationkey
     and su_nationkey = n_nationkey
     and n_regionkey = r_regionkey
     and r_name = 'Europe'
     and o_entry_d >= '2015-01-02 00:00:00.000000'
group by n_name
order by revenue desc LIMIT 10;
