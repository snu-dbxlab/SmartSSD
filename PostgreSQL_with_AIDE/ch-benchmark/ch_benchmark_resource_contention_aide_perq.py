#!/usr/bin/python3

import os
import sys
import random
import atexit
import signal
import subprocess
import psycopg2
import time, threading
import pathlib
from datetime import datetime

import json
import fileinput
import re

current_workdir = os.getcwd()
aide_queries_path = current_workdir + "/../ndp_pgsql_script/PostgreSQL/ch-queries/q"
vanilla_queries_path = current_workdir + "/../ndp_pgsql_script/PostgreSQL/ch-queries-no-hint/q"

sent_query_amount = 0
is_terminated = False
file_suffix="0"

RANDOM_SEED = 123
AIDE = False
num_ch_query = 22

ch_vanilla_queries_path = [vanilla_queries_path + str(x) + ".sql" for x in range(1,23)]

ch_queries_ori = [
    """
-- Q1
select   ol_number,
     sum(ol_quantity) as sum_qty,
     sum(ol_amount) as sum_amount,
     avg(ol_quantity) as avg_qty,
     avg(ol_amount) as avg_amount,
     count(*) as count_order
from     order_line
group by ol_number order by ol_number LIMIT 10;
    """,
"""
-- Q2
select      su_suppkey, su_name, n_name, i_id, i_name, su_address, su_phone, su_comment
from     item, supplier, stock, nation, region,
     (select s_i_id as m_i_id,
         min(s_quantity) as m_s_quantity
     from     stock, supplier, nation, region
     where     mod((s_w_id*s_i_id),10000)=su_suppkey
          and su_nationkey=n_nationkey
          and n_regionkey=r_regionkey
          and r_name like 'Europ%'
     group by s_i_id) m
where      i_id = s_i_id
     and mod((s_w_id * s_i_id), 10000) = su_suppkey
     and su_nationkey = n_nationkey
     and n_regionkey = r_regionkey
     and i_data like '%b'
     and r_name like 'Europ%'
     and i_id=m_i_id
     and s_quantity = m_s_quantity
order by n_name, su_name, i_id LIMIT 10;
""",
"""
-- Q3
select   ol_o_id, ol_w_id, ol_d_id,
     sum(ol_amount) as revenue, o_entry_d
from      customer, new_order, orders, order_line
where      c_state like 'A%'
     and c_id = o_c_id
     and c_w_id = o_w_id
     and c_d_id = o_d_id
     and no_w_id = o_w_id
     and no_d_id = o_d_id
     and no_o_id = o_id
     and ol_w_id = o_w_id
     and ol_d_id = o_d_id
     and ol_o_id = o_id
group by ol_o_id, ol_w_id, ol_d_id, o_entry_d
order by revenue desc, o_entry_d LIMIT 10;
""",
"""
-- Q4
select    o_ol_cnt, count(*) as order_count
from    orders
    where exists (select *
            from order_line
            where o_id = ol_o_id
            and o_w_id = ol_w_id
            and o_d_id = ol_d_id
            and ol_delivery_d >= o_entry_d)
group    by o_ol_cnt
order    by o_ol_cnt LIMIT 10;
""",
"""
-- Q5
select     n_name,
     sum(ol_amount) as revenue
from     customer, orders, order_line, stock, supplier, nation, region
where     c_id = o_c_id
     and c_w_id = o_w_id
     and c_d_id = o_d_id
     and ol_o_id = o_id
     and ol_w_id = o_w_id
     and ol_d_id=o_d_id
     and ol_w_id = s_w_id
     and ol_i_id = s_i_id
     and mod((s_w_id * s_i_id),10000) = su_suppkey
     and ascii(substr(c_state,1,1)) = su_nationkey
     and su_nationkey = n_nationkey
     and n_regionkey = r_regionkey
     and r_name = 'Europe'
     and o_entry_d >= '2015-01-02 00:00:00.000000'
group by n_name
order by revenue desc LIMIT 10;
""",
"""
-- Q6
select    sum(ol_amount) as revenue
from order_line
where ol_quantity between 1 and 100000 LIMIT 10;
""",
"""
-- Q7
select     su_nationkey as supp_nation,
     substr(c_state,1,1) as cust_nation,
     extract(year from o_entry_d) as l_year,
     sum(ol_amount) as revenue
from     supplier, stock, order_line, orders, customer, nation n1, nation n2
where     ol_supply_w_id = s_w_id
     and ol_i_id = s_i_id
     and mod((s_w_id * s_i_id), 10000) = su_suppkey
     and ol_w_id = o_w_id
     and ol_d_id = o_d_id
     and ol_o_id = o_id
     and c_id = o_c_id
     and c_w_id = o_w_id
     and c_d_id = o_d_id
     and su_nationkey = n1.n_nationkey
     and ascii(substr(c_state,1,1)) = n2.n_nationkey
     and (
        (n1.n_name = 'Germany' and n2.n_name = 'Cambodia')
         or
        (n1.n_name = 'Cambodia' and n2.n_name = 'Germany')
         )
group by su_nationkey, substr(c_state,1,1), extract(year from o_entry_d)
order by su_nationkey, cust_nation, l_year LIMIT 10;
""",
"""
-- Q8
select     extract(year from o_entry_d) as l_year,
     sum(case when n2.n_name = 'Germany' then ol_amount else 0 end) / sum(ol_amount) as mkt_share
from     item, supplier, stock, order_line, orders, customer, nation n1, nation n2, region
where     i_id = s_i_id
     and ol_i_id = s_i_id
     and ol_supply_w_id = s_w_id
     and mod((s_w_id * s_i_id),10000) = su_suppkey
     and ol_w_id = o_w_id
     and ol_d_id = o_d_id
     and ol_o_id = o_id
     and c_id = o_c_id
     and c_w_id = o_w_id
     and c_d_id = o_d_id
     and n1.n_nationkey = ascii(substr(c_state,1,1))
     and n1.n_regionkey = r_regionkey
     and ol_i_id < 1000
     and r_name = 'Europe'
     and su_nationkey = n2.n_nationkey
     and i_data like '%b'
     and i_id = ol_i_id
group by extract(year from o_entry_d)
order by l_year LIMIT 10;
""",
"""
-- Q9
select     n_name, extract(year from o_entry_d) as l_year, sum(ol_amount) as sum_profit
from     item, stock, supplier, order_line, orders, nation
where     ol_i_id = s_i_id
     and ol_supply_w_id = s_w_id
     and mod((s_w_id * s_i_id), 10000) = su_suppkey
     and ol_w_id = o_w_id
     and ol_d_id = o_d_id
     and ol_o_id = o_id
     and ol_i_id = i_id
     and su_nationkey = n_nationkey
     and i_data like '%BB'
group by n_name, extract(year from o_entry_d)
order by n_name, l_year desc LIMIT 10;
""",
"""
-- Q10
select     c_id, c_last, sum(ol_amount) as revenue, c_city, c_phone, n_name
from     customer, orders, order_line, nation
where     c_id = o_c_id
     and c_w_id = o_w_id
     and c_d_id = o_d_id
     and ol_w_id = o_w_id
     and ol_d_id = o_d_id
     and ol_o_id = o_id
     and o_entry_d <= ol_delivery_d
     and n_nationkey = ascii(substr(c_state,1,1))
group by c_id, c_last, c_city, c_phone, n_name
order by revenue desc LIMIT 10;
""",
"""
-- Q11
select     s_i_id, sum(s_order_cnt) as ordercount
from     stock, supplier, nation
where     mod((s_w_id * s_i_id),10000) = su_suppkey
     and su_nationkey = n_nationkey
     and n_name = 'Germany'
group by s_i_id
having   sum(s_order_cnt) >
        (select sum(s_order_cnt) * .005
        from stock, supplier, nation
        where mod((s_w_id * s_i_id),10000) = su_suppkey
        and su_nationkey = n_nationkey
        and n_name = 'Germany')
order by ordercount desc LIMIT 10;
""",
"""
-- Q12
select     o_ol_cnt,
     sum(case when o_carrier_id = 1 or o_carrier_id = 2 then 1 else 0 end) as high_line_count,
     sum(case when o_carrier_id <> 1 and o_carrier_id <> 2 then 1 else 0 end) as low_line_count
from     orders, order_line
where     ol_w_id = o_w_id
     and ol_d_id = o_d_id
     and ol_o_id = o_id
     and o_entry_d <= ol_delivery_d
group by o_ol_cnt
order by o_ol_cnt LIMIT 10;
""",
"""
-- Q13
select     c_count, count(*) as custdist
from     (select c_id, count(o_id)
     from customer left outer join orders on (
        c_w_id = o_w_id
        and c_d_id = o_d_id
        and c_id = o_c_id
        and o_carrier_id > 8)
     group by c_id) as c_orders (c_id, c_count)
group by c_count
order by custdist desc, c_count desc LIMIT 10;
""",
"""
-- Q14
select    100.00 * sum(case when i_data like 'PR%' then ol_amount else 0 end) / (1+sum(ol_amount)) as promo_revenue
from order_line, item
where ol_i_id = i_id
    LIMIT 10;
""",
"""
-- Q15
with     revenue (supplier_no, total_revenue) as (
     select mod((s_w_id * s_i_id),10000) as supplier_no,
        sum(ol_amount) as total_revenue
     from order_line, stock
        where ol_i_id = s_i_id and ol_supply_w_id = s_w_id
     group by mod((s_w_id * s_i_id),10000))
select     su_suppkey, su_name, su_address, su_phone, total_revenue
from     supplier, revenue
where     su_suppkey = supplier_no
     and total_revenue = (select max(total_revenue) from revenue)
order by su_suppkey LIMIT 10;
""",
"""
-- Q16
select     i_name,
     substr(i_data, 1, 3) as brand,
     i_price,
     count(distinct (mod((s_w_id * s_i_id),10000))) as supplier_cnt
from     stock, item
where     i_id = s_i_id
     and i_data not like 'zz%'
     and (mod((s_w_id * s_i_id),10000) not in
        (select su_suppkey
         from supplier
         where su_comment like '%bad%'))
group by i_name, substr(i_data, 1, 3), i_price
order by supplier_cnt desc LIMIT 10;
""",
"""
-- Q17
select    sum(ol_amount) / 2.0 as avg_yearly
from order_line, (select   i_id, avg(ol_quantity) as a
            from     item, order_line
            where    i_data like '%b'
                 and ol_i_id = i_id
            group by i_id) t
where ol_i_id = t.i_id
    and ol_quantity < t.a LIMIT 10;
""",
"""
-- Q18
select     c_last, c_id o_id, o_entry_d, o_ol_cnt, sum(ol_amount)
from     customer, orders, order_line
where     c_id = o_c_id
     and c_w_id = o_w_id
     and c_d_id = o_d_id
     and ol_w_id = o_w_id
     and ol_d_id = o_d_id
     and ol_o_id = o_id
group by o_id, o_w_id, o_d_id, c_id, c_last, o_entry_d, o_ol_cnt
having     sum(ol_amount) > 200
order by sum(ol_amount) desc, o_entry_d LIMIT 10;
""",
"""
-- Q19
select    sum(ol_amount) as revenue
from order_line, item
where    (
      ol_i_id = i_id
          and i_data like '%a'
          and ol_quantity >= 1
          and ol_quantity <= 10
          and i_price between 1 and 400000
          and ol_w_id in (1,2,3)
    ) or (
      ol_i_id = i_id
      and i_data like '%b'
      and ol_quantity >= 1
      and ol_quantity <= 10
      and i_price between 1 and 400000
      and ol_w_id in (1,2,4)
    ) or (
      ol_i_id = i_id
      and i_data like '%c'
      and ol_quantity >= 1
      and ol_quantity <= 10
      and i_price between 1 and 400000
      and ol_w_id in (1,5,3)
    ) LIMIT 10;
""",
"""
-- Q20
select   su_name, su_address
from     supplier, nation
where    su_suppkey in
        (select  mod(s_i_id * s_w_id, 10000)
        from     stock, order_line
        where    s_i_id in
                (select i_id
                 from item
                 where i_data like 'co%')
             and ol_i_id=s_i_id
        group by s_i_id, s_w_id, s_quantity
        having   2*s_quantity > sum(ol_quantity))
     and su_nationkey = n_nationkey
     and n_name = 'Germany'
order by su_name LIMIT 10;
""",
"""
-- Q21
select     su_name, count(*) as numwait
from     supplier, order_line l1, orders, stock, nation
where     ol_o_id = o_id
     and ol_w_id = o_w_id
     and ol_d_id = o_d_id
     and ol_w_id = s_w_id
     and ol_i_id = s_i_id
     and mod((s_w_id * s_i_id),10000) = su_suppkey
     and l1.ol_delivery_d > o_entry_d
     and not exists (select *
             from order_line l2
             where  l2.ol_o_id = l1.ol_o_id
                and l2.ol_w_id = l1.ol_w_id
                and l2.ol_d_id = l1.ol_d_id
                and l2.ol_delivery_d > l1.ol_delivery_d)
     and su_nationkey = n_nationkey
     and n_name = 'Germany'
group by su_name
order by numwait desc, su_name LIMIT 10;
""",
"""
-- Q22
select     substr(c_state,1,1) as country,
     count(*) as numcust,
     sum(c_balance) as totacctbal
from     customer
where     substr(c_phone,1,1) in ('1','2','3','4','5','6','7')
     and c_balance > (select avg(c_BALANCE)
              from      customer
              where  c_balance > 0.00
                  and substr(c_phone,1,1) in ('1','2','3','4','5','6','7'))
     and not exists (select *
             from    orders
             where    o_c_id = c_id
                     and o_w_id = c_w_id
                    and o_d_id = c_d_id)
group by substr(c_state,1,1)
order by substr(c_state,1,1) LIMIT 10;
"""
]

# Client for running long joins on sysbench
class Client(threading.Thread):
    def __init__(self, client_id, autocommit, result_file, aide, group, group_query):
        global ch_vanilla_queries_path
        global aide_queries_path

        threading.Thread.__init__(self)

        self.client_id = client_id
        self.autocommit = autocommit
        self.result_file = result_file
        self.aide = aide
        self.group = group
        self.group_query = group_query

        self.db = self.make_connector()
        self.db.set_session(autocommit=self.autocommit)
        self.cursor = self.db.cursor()
        self.end = False
        self.group = group

        self.ch_queries = []
        self.query_num = 22
        self.group_query_num = []

        self.ch_aide_queries_path = []
        if self.aide:
            if self.group == 0:
                self.query_num = 22
                self.query_seq =[x for x in range(1,23)]
                self.ch_aide_queries_path = [aide_queries_path + str(x) + ".sql" for x in range(1,23)]
            elif self.group == 1:
                self.query_num = 7
                self.query_seq = [2, 5, 8, 9, 11, 21, 20]
            elif self.group == 2:
                self.query_num = 2
                self.query_seq = [15, 16]
            elif self.group == 3:
                self.query_num = 7
                self.query_seq = [3, 10, 12, 14, 17, 18, 19]
            elif self.group == 4:
                self.query_num = 5
                self.query_seq = [1, 4, 6, 13, 22]
            else:
                assert 0, "input incorrect group\n"

            self.ch_aide_queries_path = [aide_queries_path + str(x) + ".sql" for x in self.query_seq]

            for query_path in self.ch_aide_queries_path:
                f_query = open(query_path, 'r')
                f_contents = f_query.read()
                self.ch_queries.append(f_contents)
                f_query.close()
        else:
            for query_path in ch_vanilla_queries_path:
                f_query = open(query_path, 'r')
                f_contents = f_query.read()
                self.ch_queries.append(f_contents)
                f_query.close()

    def terminate(self):
        if self.end is False:
            self.end = True

    def run(self):
        global is_terminated
        global num_ch_query

        if self.group_query == True:
            idx = 0
        else:
            idx = self.client_id - 1

        times = 0
        if self.aide:
            self.cursor.execute('SELECT pg_enable_ndp();')
        else:
            self.cursor.execute('SET enable_mergejoin = on;')                  
            self.cursor.execute('SET enable_nestloop = on;')
            self.cursor.execute('SET enable_indexscan = on;')
            self.cursor.execute('SET enable_bitmapscan = on;')
            self.cursor.execute('SET enable_seqscan = on;')
            self.cursor.execute('SELECT pg_disable_ndp();')

        with open(self.result_file, 'w') as f:
            epoch = time.perf_counter()

            while not self.end:
                start_time = time.perf_counter()

                query = self.make_query(idx)
                self.cursor.execute(query)

                self.cursor.fetchall()

                end_time = time.perf_counter()


                if self.group_query == True:
                    results = "Q" + str(self.query_seq[idx]) + ' ' + str(times) + ' ' +  f'{(end_time - start_time):.3f}\n'
                else:
                    results = str(times) + ' ' +  f'{(end_time - start_time):.3f}\n'

                f.write(results)
                f.flush()
                    
                times += 1

                if self.group_query == True:
                    idx += 1
                    idx %= self.query_num

            self.db.commit()
            self.cursor.close()
            self.db.close()

    def make_query(self, idx):
        return self.ch_queries[idx] 

    def make_connector(self):
        return psycopg2.connect(host=os.environ['PGHOST'],
                dbname=os.environ['PGDATABASE'],
                user=os.environ['PGUSER'],
                port=os.environ['PGPORT'])

def give_stats(sent_query_amount, time_lapsed_in_secs, dir_path):
    with open(dir_path + "/ch_results_{}.txt".format(file_suffix), "w") as f:
        f.write("queries {} in {} seconds\n".format(sent_query_amount, time_lapsed_in_secs))
        f.write("QPH {}\n".format(3600.0 * sent_query_amount / time_lapsed_in_secs))

def get_curtime_in_seconds():
    return int(round(time.time()))

def terminate(dir_path):
    global is_terminated
    global sent_query_amount
    global start_time_in_secs

    end_time_in_secs = get_curtime_in_seconds()

    give_stats(sent_query_amount, end_time_in_secs - start_time_in_secs, dir_path)

    is_terminated = True

class GracefulKiller:
    kill_now = False
    def __init__(self, dir_path):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.dir_path = dir_path

    def exit_gracefully(self,signum, frame):
        global is_terminated
        self.kill_now = True
        print("got a kill signal")
        terminate(dir_path)

if __name__ == "__main__":
    long_thread_count = int(sys.argv[1])
    short_thread_count = int(sys.argv[2])
    aide_thread_count = 0
    is_group = False
    coord_ip = sys.argv[3]
    initial_sleep_in_mins=int(sys.argv[4])

    ISAIDE=sys.argv[5]
    ISGROUP=sys.argv[6]
    
    query_num = int(sys.argv[7])

    aide_id = 1
    aide_num = 0


    if ISAIDE == "true":
        aide_thread_count = 1
        if ISGROUP == "true":
            is_group = True
            aide_num = query_num
        else:
            aide_id = query_num
        
    dir_path = sys.argv[8]

    file_suffix=sys.argv[9] + "_"
    file_suffix+=datetime.now().strftime('%Y-%m-%d_%I:%M:%S_%p')

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    short_file_path = dir_path + "/ch_queries_{}_short_worker#{}.txt"
    long_file_path = dir_path + "/ch_queries_{}_long_worker#{}.txt"
    aide_file_path = dir_path + "/aide_ch_queries_{}_aide_worker#{}.txt"

    random.seed(RANDOM_SEED)

    time.sleep(initial_sleep_in_mins * 60)
    start_time_in_secs = get_curtime_in_seconds()

    short_olap = [Client(client_id = i, autocommit=True, result_file=os.path.join(short_file_path.format(file_suffix, i)), aide=False, group=-1, group_query = False) \
            for i in range(1, short_thread_count + 1)]

    long_olap = [Client(client_id = i, autocommit=False, result_file=os.path.join(long_file_path.format(file_suffix, i)), aide=False, group=-1, group_query = False) \
            for i in range(1, long_thread_count + 1)]

    aide_olap = [Client(client_id = aide_id, autocommit=False, result_file=os.path.join(aide_file_path.format(file_suffix, aide_id)), aide=True, group=aide_num, group_query = is_group) \
            for i in range(1, aide_thread_count + 1)]

    for short_client in short_olap:
        short_client.start()

    for long_client in long_olap:
        long_client.start()

    if aide_thread_count == 1:
        aide_olap[0].start()

    killer = GracefulKiller(dir_path)
    while not killer.kill_now:
        time.sleep(10)

    for short_client in short_olap:
        short_client.terminate()
    for long_client in long_olap:
        long_client.terminate()

    if aide_thread_count == 1:
        aide_olap[0].terminate()

    for short_client in short_olap:
        short_client.join()
    for long_client in long_olap:
        long_client.join()

    if aide_thread_count == 1:
        aide_olap[0].join()
