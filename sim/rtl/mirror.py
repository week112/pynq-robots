# Cycle-level Python mirror of imu_reader.v (engine + sequencer + pipeline math) with a behavioural MPU6050 slave.
# Purpose: catch protocol / sequencing / scaling bugs before the design goes to Vivado.
import sys
CLK_HZ=100_000_000; I2C_HZ=400_000; SAMPLE_US=2000; PWRUP_US=300; CAL_SHIFT=3; AUTO_CAL_AT=5; DLPF=3; DEV=0x68
US_DIV=CLK_HZ//1_000_000; QDIV=CLK_HZ//(4*I2C_HZ); CAL_N=1<<CAL_SHIFT
K_C=(1073741824*SAMPLE_US)//131000
OP_START,OP_WR,OP_RDA,OP_RDN,OP_STOP=0,1,2,3,4
def rom(script,pc):
    if script==0:
        regs=[(0x6B,0x01),(0x1A,DLPF),(0x19,0),(0x1B,0),(0x1C,0)]
        t=[]
        for r,v in regs: t+= [(0,OP_START,0),(0,OP_WR,DEV<<1),(0,OP_WR,r),(0,OP_WR,v),(0,OP_STOP,0)]
        t+=[(0,OP_START,0),(0,OP_WR,DEV<<1),(0,OP_WR,0x75),(0,OP_START,0),(0,OP_WR,(DEV<<1)|1),(0,OP_RDN,0),(1,OP_STOP,0)]
    else:
        t=[(0,OP_START,0),(0,OP_WR,DEV<<1),(0,OP_WR,0x3B),(0,OP_START,0),(0,OP_WR,(DEV<<1)|1)]+[(0,OP_RDA,0)]*13+[(0,OP_RDN,0),(1,OP_STOP,0)]
    return t[pc] if pc<len(t) else (1,OP_STOP,0)

class Slave:
    def __init__(s):
        s.mem=[0]*256; s.mem[0x75]=0x68
        data=[0x01,0x23,0x04,0x56,0x40,0x00,0x0a,0xbc,0x00,0x11,0xff,0xee,0x00,0x64]
        for i,b in enumerate(data): s.mem[0x3B+i]=b
        s.low=0; s.active=0; s.mode=0; s.stage=0; s.n=0; s.rxb=0; s.txb=0; s.ptr=0; s.rw=0; s.m_ack=0
        s.pscl=1; s.psda=1; s.log=[]
    def step(s,scl,sda):   # scl, sda: resolved line values this clock
        if s.psda==1 and sda==0 and scl==1:  # START
            s.active=1; s.mode=0; s.stage=0; s.n=0; s.low=0; s.log.append('S')
        if s.psda==0 and sda==1 and scl==1:  # STOP
            s.active=0; s.low=0; s.mode=0; s.n=0; s.log.append('P')
        if s.pscl==0 and scl==1 and s.active:   # rising
            if not s.mode:
                if s.n<8: s.rxb=((s.rxb<<1)|sda)&0xff
            else:
                if s.n==8: s.m_ack=1-sda
            if s.n<9: s.n+=1
        if s.pscl==1 and scl==0 and s.active:   # falling
            if not s.mode:
                if s.n==8:
                    if s.stage==0:
                        if (s.rxb>>1)==DEV: s.low=1; s.rw=s.rxb&1; s.log.append('A%02x'%s.rxb)
                        else: s.low=0; s.active=0
                    elif s.stage==1: s.ptr=s.rxb; s.low=1; s.log.append('R%02x'%s.rxb)
                    else: s.mem[s.ptr]=s.rxb; s.log.append('W%02x=%02x'%(s.ptr,s.rxb)); s.ptr=(s.ptr+1)&0xff; s.low=1
                elif s.n==9:
                    s.low=0; s.n=0
                    if s.stage==0:
                        if s.rw:
                            s.mode=1; s.txb=s.mem[s.ptr]; s.low=1-((s.txb>>7)&1); s.ptr=(s.ptr+1)&0xff
                        else: s.stage=1
                    elif s.stage==1: s.stage=2
            else:
                if 1<=s.n<=7: s.low=1-((s.txb>>(7-s.n))&1)
                elif s.n==8: s.low=0
                elif s.n==9:
                    if s.m_ack:
                        s.n=0; s.txb=s.mem[s.ptr]; s.ptr=(s.ptr+1)&0xff; s.low=1-((s.txb>>7)&1)
                    else: s.mode=0; s.active=0; s.low=0
        s.pscl=scl; s.psda=sda

def run(max_us):
    sl=Slave()
    # DUT regs
    us_div=0; us_tick=0; now_us=0; per_cnt=0
    scl_val=1; sda_val=1; sda_sync=[1,1]
    eng_go=0; op_in=0; arg_in=0; eng_busy=0; eng_done=0; eng_ack=0; eng_op=0; eng_tx=0; eng_rxsh=0; eng_bit=0; eng_ph=0; qcnt=0
    st=0; script=0; pc=0; rxi=0; pwr_cnt=0; rom_last=0; nack_run=0; sample_req=0
    rx=[0]*14; who=0; init_done=0; who_ok=0; nack_last=0; miss=0; commit_start=0; ts_lat=0; n_cnt=0; n_lat=0
    calibrating=0; calibrated=0; bias=0; acc=0; seq=0; cal_cnt=0; cal_sum=0; auto_done=0; int_en=0
    yaw_hist=[]; commits=[]; ts_hist=[]
    cycles=max_us*US_DIV
    for cyc in range(cycles):
        # resolved lines from current regs
        scl=scl_val; sda=1 if (sda_val and not sl.low) else 0
        sl.step(scl,sda)
        sda=1 if (sda_val and not sl.low) else 0
        # ---------- next-state computation (non-blocking semantics)
        n_us_div=us_div; n_us_tick=0; n_now=now_us
        if us_div==US_DIV-1: n_us_div=0; n_us_tick=1; n_now=now_us+1
        else: n_us_div=us_div+1
        period_boundary = us_tick and per_cnt==SAMPLE_US-1
        n_per=per_cnt
        if us_tick: n_per=0 if per_cnt==SAMPLE_US-1 else per_cnt+1
        n_sync=[sda_sync[1-1+0] if False else sda, sda_sync[0]]  # {sda_sync[0], sda} -> [1]=sda_sync[0],[0]=sda
        n_sync=[sda,sda_sync[0]]  # index0 = newest
        sda_in=sda_sync[1]
        qtick = (qcnt==QDIV-1)
        n_qcnt = 0 if (not eng_busy or qtick) else qcnt+1
        # engine
        n=dict(eng_busy=eng_busy,eng_done=0,eng_ack=eng_ack,eng_op=eng_op,eng_tx=eng_tx,eng_rxsh=eng_rxsh,eng_bit=eng_bit,eng_ph=eng_ph,scl_val=scl_val,sda_val=sda_val)
        if eng_go and not eng_busy:
            n.update(eng_busy=1,eng_op=op_in,eng_tx=arg_in,eng_bit=0,eng_ph=0)
        elif eng_busy and qtick:
            n['eng_ph']=(eng_ph+1)&3
            if eng_op==OP_START:
                if eng_ph==0: n['scl_val']=0
                elif eng_ph==1: n['sda_val']=1
                elif eng_ph==2: n['scl_val']=1
                else: n.update(sda_val=0,eng_busy=0,eng_done=1)
            elif eng_op==OP_STOP:
                if eng_ph==0: n['scl_val']=0
                elif eng_ph==1: n['sda_val']=0
                elif eng_ph==2: n['scl_val']=1
                else: n.update(sda_val=1,eng_busy=0,eng_done=1)
            else:
                if eng_ph==0: n['scl_val']=0
                elif eng_ph==1:
                    if eng_op==OP_WR: n['sda_val']=(eng_tx>>7)&1 if eng_bit<8 else 1
                    else: n['sda_val']=1 if eng_bit<8 else (1 if eng_op==OP_RDN else 0)
                elif eng_ph==2: n['scl_val']=1
                else:
                    if eng_bit<8:
                        if eng_op==OP_WR: n['eng_tx']=(eng_tx<<1)&0xff
                        else: n['eng_rxsh']=((eng_rxsh<<1)|sda_in)&0xff
                    elif eng_op==OP_WR: n['eng_ack']=sda_in
                    if eng_bit==8: n.update(eng_busy=0,eng_done=1)
                    n['eng_bit']=eng_bit+1
        # sequencer
        s_st=st; s_script=script; s_pc=pc; s_rxi=rxi; s_pwr=pwr_cnt; s_rl=rom_last; s_nack=nack_run; s_sreq=sample_req
        s_op=op_in; s_arg=arg_in; s_go=0; s_who=who; s_init=init_done; s_whook=who_ok; s_nl=nack_last; s_miss=miss
        s_commit=0; s_tslat=ts_lat; s_ncnt=n_cnt; s_nlat=n_lat; s_rx=None
        ok_now=0
        if st==0:
            if us_tick:
                if pwr_cnt>=PWRUP_US: s_pwr=0; s_script=0; s_pc=0; s_nack=0; s_st=1
                else: s_pwr=pwr_cnt+1
        elif st==1:
            l,o,a=rom(script,pc); s_rl=l; s_op=o; s_arg=a; s_go=1; s_st=2
        elif st==2 and eng_done:
            if op_in==OP_WR and eng_ack: s_nack=1
            if op_in in (OP_RDA,OP_RDN):
                if script: s_rx=(rxi,eng_rxsh); s_rxi=rxi+1
                else: s_who=eng_rxsh
            if not rom_last: s_pc=pc+1; s_st=1
            else:
                s_st=3
                if not script:
                    if (not nack_run) and who!=0 and who!=0xFF: s_init=1; s_whook=1
                    else: s_st=0; s_pwr=0
                else:
                    if nack_run:
                        s_nl=1; s_miss=min(255,miss+1)
                    else:
                        s_nl=0; s_commit=1; s_nlat=n_cnt; ok_now=1
        elif st==3:
            if sample_req and init_done:
                s_sreq=0; s_script=1; s_pc=0; s_rxi=0; s_nack=0; s_tslat=now_us; s_st=1
        if period_boundary: s_sreq=1
        if ok_now: s_ncnt=1 if period_boundary else 0
        elif period_boundary: s_ncnt=15 if n_cnt==15 else n_cnt+1
        # pipeline (collapsed): at commit_start -> do the math for that sample
        if commit_start:
            gz=(rx[12]<<8)|rx[13]; gz=gz-65536 if gz>=32768 else gz
            int_en_l = 1 if (calibrated and not calibrating) else 0
            if calibrating:
                cal_sum+=gz; cal_cnt+=1
                if cal_cnt==CAL_N: bias=cal_sum>>CAL_SHIFT; calibrating=0; calibrated=1; acc=0
            if int_en_l:
                acc+=(gz-bias)*K_C*n_lat
            yaw=(acc>>30)
            seq+=1
            commits.append((now_us,ts_lat,seq,yaw,gz,bias,n_lat,[ (rx[0]<<8)|rx[1] ]))
            if (not auto_done) and seq-1==AUTO_CAL_AT:
                auto_done=1; calibrating=1; calibrated=0; cal_cnt=0; cal_sum=0
        # ---------- commit registers
        us_div=n_us_div; us_tick=n_us_tick; now_us=n_now; per_cnt=n_per; sda_sync=n_sync; qcnt=n_qcnt
        eng_busy=n['eng_busy']; eng_done=n['eng_done']; eng_ack=n['eng_ack']; eng_op=n['eng_op']; eng_tx=n['eng_tx']
        eng_rxsh=n['eng_rxsh']; eng_bit=n['eng_bit']; eng_ph=n['eng_ph']; scl_val=n['scl_val']; sda_val=n['sda_val']
        eng_go=s_go
        st=s_st; script=s_script; pc=s_pc; rxi=s_rxi; pwr_cnt=s_pwr; rom_last=s_rl; nack_run=s_nack; sample_req=s_sreq
        op_in=s_op; arg_in=s_arg; who=s_who; init_done=s_init; who_ok=s_whook; nack_last=s_nl; miss=s_miss
        commit_start=s_commit; ts_lat=s_tslat; n_cnt=s_ncnt; n_lat=s_nlat
        if s_rx: rx[s_rx[0]]=s_rx[1]
        # testbench behaviour: after calibrated, bump gz in slave memory
        if calibrated and sl.mem[0x48]==0x64 and not getattr(run,'bumped',0):
            run.bumped=1; sl.mem[0x47]=0x05; sl.mem[0x48]=0x82   # 1410
            run.bump_seq=seq
    return sl,commits

sl,commits=run(int(sys.argv[1]) if len(sys.argv)>1 else 30000)
print("slave log (first 60):",' '.join(sl.log[:60]))
print("mem 6B,1A,19,1B,1C:",[hex(sl.mem[a]) for a in (0x6B,0x1A,0x19,0x1B,0x1C)])
print("commits:",len(commits))
for c in commits[:3]+commits[-3:]: print(c)
print("bump at seq",getattr(run,'bump_seq',None))
