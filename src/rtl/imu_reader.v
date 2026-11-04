`timescale 1ns / 1ps
// ============================================================================
// imu_reader : PL-side MPU6050 reader (I2C master + timestamp + gyro-Z yaw integrator)
//
//  * I2C master (open drain) polls registers 0x3B..0x48 (accel, temp, gyro) every SAMPLE_US
//  * 1 us free-running timestamp counter; every sample is stamped when its I2C burst starts
//  * Gyro-Z bias calibration (2^CAL_SHIFT samples, automatic after AUTO_CAL_AT samples,
//    or on a rising edge of cfg_word[16]) and fixed-point yaw integration (milli-degrees)
//  * All results are committed in ONE clock cycle together with a sequence counter,
//    so software can use a seqlock (read seq, read data, read seq again) for a consistent snapshot
//
//  cfg_word  [9:0]  : min_duty for motor_ctrl (ignored here)
//            [14:12]: raw_word select  0:{ax,ay} 1:{az,temp} 2:{gx,gy} 3:{gz,bias} 4:{24'b0,who_am_i}
//                       5:{attempts,nack_cnt,2'b0,nack_pc,st,script,pc}  6:{30'b0,sda_pin,scl_pin}
//            [16]   : rising edge = start gyro bias calibration (keep the robot still)
//  stat_word [0] init_done  [1] who_ok  [2] calibrating  [3] calibrated  [4] last_poll_nack
//            [15:8] miss (failed polls, saturating)   [31:16] seq
//  yaw_word  : signed yaw angle in milli-degrees
//  ts_word   : us timestamp of the most recent sample (start of its I2C burst)
//  now_word  : free-running us counter (same time base, for aligning camera frames)
// ============================================================================
module imu_reader #(
    parameter integer CLK_HZ      = 100_000_000,
    parameter integer I2C_HZ      = 400_000,
    parameter integer SAMPLE_US   = 2000,
    parameter integer PWRUP_US    = 100_000,
    parameter integer CAL_SHIFT   = 8,
    parameter integer AUTO_CAL_AT = 50,
    parameter [7:0]   DLPF_CFG    = 8'd3,
    parameter [6:0]   DEV_ADDR    = 7'h68
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] cfg_word,
    inout  wire        scl,
    inout  wire        sda,
    output wire [31:0] ts_word,
    output wire [31:0] stat_word,
    output wire [31:0] yaw_word,
    output wire [31:0] raw_word,
    output wire [31:0] now_word
);
    localparam integer US_DIV = CLK_HZ / 1_000_000;
    localparam integer QDIV   = CLK_HZ / (4 * I2C_HZ);
    localparam integer CAL_N  = (1 << CAL_SHIFT);
    // yaw increment per sample, in 2^-30 milli-degree units, for 131 LSB/(deg/s)
    localparam [24:0]  K_C    = (64'd1073741824 * SAMPLE_US) / 64'd131000;

    localparam [2:0] OP_START = 3'd0, OP_WR = 3'd1, OP_RDA = 3'd2, OP_RDN = 3'd3, OP_STOP = 3'd4;

    // ------------------------------------------------------------------ script ROM
    // {last, op[2:0], arg[7:0]}
    function [11:0] rom;
        input        script;   // 0 = init, 1 = poll
        input [5:0]  pc;
        begin
            rom = {1'b1, OP_STOP, 8'h00};
        if (!script) begin
            case (pc)
                6'd0: rom = {1'b0, OP_START, 8'h00};
                6'd1: rom = {1'b0, OP_WR, DEV_ADDR, 1'b0};
                6'd2: rom = {1'b0, OP_WR, 8'h6B};
                6'd3: rom = {1'b0, OP_WR, 8'h01};
                6'd4: rom = {1'b0, OP_STOP, 8'h00};
                6'd5: rom = {1'b0, OP_START, 8'h00};
                6'd6: rom = {1'b0, OP_WR, DEV_ADDR, 1'b0};
                6'd7: rom = {1'b0, OP_WR, 8'h1A};
                6'd8: rom = {1'b0, OP_WR, DLPF_CFG};
                6'd9: rom = {1'b0, OP_STOP, 8'h00};
                6'd10: rom = {1'b0, OP_START, 8'h00};
                6'd11: rom = {1'b0, OP_WR, DEV_ADDR, 1'b0};
                6'd12: rom = {1'b0, OP_WR, 8'h19};
                6'd13: rom = {1'b0, OP_WR, 8'h00};
                6'd14: rom = {1'b0, OP_STOP, 8'h00};
                6'd15: rom = {1'b0, OP_START, 8'h00};
                6'd16: rom = {1'b0, OP_WR, DEV_ADDR, 1'b0};
                6'd17: rom = {1'b0, OP_WR, 8'h1B};
                6'd18: rom = {1'b0, OP_WR, 8'h00};
                6'd19: rom = {1'b0, OP_STOP, 8'h00};
                6'd20: rom = {1'b0, OP_START, 8'h00};
                6'd21: rom = {1'b0, OP_WR, DEV_ADDR, 1'b0};
                6'd22: rom = {1'b0, OP_WR, 8'h1C};
                6'd23: rom = {1'b0, OP_WR, 8'h00};
                6'd24: rom = {1'b0, OP_STOP, 8'h00};
                6'd25: rom = {1'b0, OP_START, 8'h00};
                6'd26: rom = {1'b0, OP_WR, DEV_ADDR, 1'b0};
                6'd27: rom = {1'b0, OP_WR, 8'h75};
                6'd28: rom = {1'b0, OP_START, 8'h00};
                6'd29: rom = {1'b0, OP_WR, DEV_ADDR, 1'b1};
                6'd30: rom = {1'b0, OP_RDN, 8'h00};
                6'd31: rom = {1'b1, OP_STOP, 8'h00};
                default: rom = {1'b1, OP_STOP, 8'h00};
            endcase
        end else begin
            case (pc)
                6'd0: rom = {1'b0, OP_START, 8'h00};
                6'd1: rom = {1'b0, OP_WR, DEV_ADDR, 1'b0};
                6'd2: rom = {1'b0, OP_WR, 8'h3B};
                6'd3: rom = {1'b0, OP_START, 8'h00};
                6'd4: rom = {1'b0, OP_WR, DEV_ADDR, 1'b1};
                6'd5: rom = {1'b0, OP_RDA, 8'h00};
                6'd6: rom = {1'b0, OP_RDA, 8'h00};
                6'd7: rom = {1'b0, OP_RDA, 8'h00};
                6'd8: rom = {1'b0, OP_RDA, 8'h00};
                6'd9: rom = {1'b0, OP_RDA, 8'h00};
                6'd10: rom = {1'b0, OP_RDA, 8'h00};
                6'd11: rom = {1'b0, OP_RDA, 8'h00};
                6'd12: rom = {1'b0, OP_RDA, 8'h00};
                6'd13: rom = {1'b0, OP_RDA, 8'h00};
                6'd14: rom = {1'b0, OP_RDA, 8'h00};
                6'd15: rom = {1'b0, OP_RDA, 8'h00};
                6'd16: rom = {1'b0, OP_RDA, 8'h00};
                6'd17: rom = {1'b0, OP_RDA, 8'h00};
                6'd18: rom = {1'b0, OP_RDN, 8'h00};
                6'd19: rom = {1'b1, OP_STOP, 8'h00};
                default: rom = {1'b1, OP_STOP, 8'h00};
            endcase
        end
        end
    endfunction

    // ------------------------------------------------------------------ time base
    reg [7:0]  us_div;
    reg        us_tick;
    reg [31:0] now_us;
    always @(posedge clk) begin
        if (!rst_n) begin
            us_div <= 8'd0; us_tick <= 1'b0; now_us <= 32'd0;
        end else begin
            us_tick <= 1'b0;
            if (us_div == US_DIV - 1) begin
                us_div <= 8'd0; us_tick <= 1'b1; now_us <= now_us + 32'd1;
            end else begin
                us_div <= us_div + 8'd1;
            end
        end
    end

    reg [15:0] per_cnt;
    always @(posedge clk) begin
        if (!rst_n) per_cnt <= 16'd0;
        else if (us_tick) per_cnt <= (per_cnt == SAMPLE_US - 1) ? 16'd0 : per_cnt + 16'd1;
    end
    wire period_boundary = us_tick && (per_cnt == SAMPLE_US - 1);

    // ------------------------------------------------------------------ I2C byte engine
    reg        scl_val, sda_val;                 // 1 = released (pulled high), 0 = driven low
    wire scl_pin, sda_pin;
`ifdef XILINX_SIMULATOR
    // simulation: behavioural open-drain (testbench provides the pull-ups)
    assign scl = scl_val ? 1'bz : 1'b0;
    assign sda = sda_val ? 1'bz : 1'b0;
    assign scl_pin = scl;
    assign sda_pin = sda;
`else
    // hardware: explicit IOBUF (T=1 -> released/high-Z, T=0 -> drive low). Needed because the
    // block design is synthesized out-of-context, where tri-state inference to IOBUF does not happen.
    IOBUF u_scl_iobuf (.O(scl_pin), .IO(scl), .I(1'b0), .T(scl_val));
    IOBUF u_sda_iobuf (.O(sda_pin), .IO(sda), .I(1'b0), .T(sda_val));
`endif
    reg [1:0]  sda_sync;
    always @(posedge clk) sda_sync <= {sda_sync[0], sda_pin};
    wire sda_in = sda_sync[1];

    reg        eng_go;
    reg [2:0]  op_in;
    reg [7:0]  arg_in;
    reg        eng_busy, eng_done, eng_ack;
    reg [2:0]  eng_op;
    reg [7:0]  eng_tx, eng_rxsh;
    reg [3:0]  eng_bit;
    reg [1:0]  eng_ph;
    reg [15:0] qcnt;
    wire       qtick = (qcnt == QDIV - 1);

    always @(posedge clk) begin
        if (!rst_n || !eng_busy || qtick) qcnt <= 16'd0;
        else qcnt <= qcnt + 16'd1;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            eng_busy <= 1'b0; eng_done <= 1'b0; eng_ack <= 1'b0;
            eng_op <= 3'd0; eng_tx <= 8'd0; eng_rxsh <= 8'd0; eng_bit <= 4'd0; eng_ph <= 2'd0;
            scl_val <= 1'b1; sda_val <= 1'b1;
        end else begin
            eng_done <= 1'b0;
            if (eng_go && !eng_busy) begin
                eng_busy <= 1'b1; eng_op <= op_in; eng_tx <= arg_in;
                eng_bit <= 4'd0; eng_ph <= 2'd0;
            end else if (eng_busy && qtick) begin
                eng_ph <= eng_ph + 2'd1;
                case (eng_op)
                    OP_START: case (eng_ph)
                        2'd0: scl_val <= 1'b0;
                        2'd1: sda_val <= 1'b1;
                        2'd2: scl_val <= 1'b1;
                        2'd3: begin sda_val <= 1'b0; eng_busy <= 1'b0; eng_done <= 1'b1; end
                    endcase
                    OP_STOP: case (eng_ph)
                        2'd0: scl_val <= 1'b0;
                        2'd1: sda_val <= 1'b0;
                        2'd2: scl_val <= 1'b1;
                        2'd3: begin sda_val <= 1'b1; eng_busy <= 1'b0; eng_done <= 1'b1; end
                    endcase
                    default: case (eng_ph)          // OP_WR / OP_RDA / OP_RDN : 9 bit cells
                        2'd0: scl_val <= 1'b0;
                        2'd1: begin
                            if (eng_op == OP_WR) sda_val <= (eng_bit < 4'd8) ? eng_tx[7] : 1'b1;
                            else                 sda_val <= (eng_bit < 4'd8) ? 1'b1 : (eng_op == OP_RDN);
                        end
                        2'd2: scl_val <= 1'b1;
                        2'd3: begin
                            if (eng_bit < 4'd8) begin
                                if (eng_op == OP_WR) eng_tx   <= {eng_tx[6:0], 1'b0};
                                else                 eng_rxsh <= {eng_rxsh[6:0], sda_in};
                            end else if (eng_op == OP_WR) begin
                                eng_ack <= sda_in;                 // 0 = ACK, 1 = NACK
                            end
                            if (eng_bit == 4'd8) begin eng_busy <= 1'b0; eng_done <= 1'b1; end
                            eng_bit <= eng_bit + 4'd1;
                        end
                    endcase
                endcase
            end
        end
    end

    // ------------------------------------------------------------------ sequencer
    localparam [1:0] ST_PWR = 2'd0, ST_ISSUE = 2'd1, ST_WAIT = 2'd2, ST_IDLE = 2'd3;
    reg [1:0]  st;
    reg        script;
    reg [5:0]  pc;
    reg [3:0]  rxi;
    reg [31:0] pwr_cnt;
    reg        rom_last, nack_run, sample_req;
    wire [11:0] rom_q = rom(script, pc);
    reg [7:0]  rx [0:13];
    reg [7:0]  who;
    reg        init_done, who_ok, nack_last;
    reg [7:0]  miss;
    reg        commit_start;
    reg [31:0] ts_lat;
    reg [3:0]  n_cnt, n_lat;
    reg        ok_now;
    reg [7:0]  attempts, nack_cnt;
    reg [5:0]  nack_pc;
    reg [1:0]  scl_sync;
    always @(posedge clk) scl_sync <= {scl_sync[0], scl_pin};

    always @(posedge clk) begin
        if (!rst_n) begin
            st <= ST_PWR; script <= 1'b0; pc <= 6'd0; rxi <= 4'd0; pwr_cnt <= 32'd0;
            rom_last <= 1'b0; nack_run <= 1'b0; sample_req <= 1'b0;
            op_in <= 3'd0; arg_in <= 8'd0; eng_go <= 1'b0;
            attempts <= 8'd0; nack_cnt <= 8'd0; nack_pc <= 6'd0;
            who <= 8'd0; init_done <= 1'b0; who_ok <= 1'b0; nack_last <= 1'b0; miss <= 8'd0;
            commit_start <= 1'b0; ts_lat <= 32'd0; n_cnt <= 4'd0; n_lat <= 4'd0;
        end else begin
            eng_go       <= 1'b0;
            commit_start <= 1'b0;
            ok_now       =  1'b0;
            case (st)
                ST_PWR: if (us_tick) begin
                    if (pwr_cnt >= PWRUP_US) begin
                        pwr_cnt <= 32'd0; script <= 1'b0; pc <= 6'd0; nack_run <= 1'b0; st <= ST_ISSUE;
                        if (attempts != 8'hFF) attempts <= attempts + 8'd1;
                    end else begin
                        pwr_cnt <= pwr_cnt + 32'd1;
                    end
                end
                ST_ISSUE: begin
                    rom_last <= rom_q[11];
                    op_in    <= rom_q[10:8];
                    arg_in   <= rom_q[7:0];
                    eng_go   <= 1'b1;
                    st       <= ST_WAIT;
                end
                ST_WAIT: if (eng_done) begin
                    if (op_in == OP_WR && eng_ack) begin
                        nack_run <= 1'b1;
                        if (!nack_run) nack_pc <= pc;
                        if (nack_cnt != 8'hFF) nack_cnt <= nack_cnt + 8'd1;
                    end
                    if (op_in == OP_RDA || op_in == OP_RDN) begin
                        if (script) begin rx[rxi] <= eng_rxsh; rxi <= rxi + 4'd1; end
                        else        who <= eng_rxsh;
                    end
                    if (!rom_last) begin
                        pc <= pc + 6'd1; st <= ST_ISSUE;
                    end else begin
                        st <= ST_IDLE;
                        if (!script) begin
                            // init finished
                            if (!nack_run && who != 8'h00 && who != 8'hFF) begin
                                init_done <= 1'b1; who_ok <= 1'b1;
                            end else begin
                                st <= ST_PWR; pwr_cnt <= 32'd0;      // retry later
                            end
                        end else begin
                            if (nack_run) begin
                                nack_last <= 1'b1;
                                if (miss != 8'hFF) miss <= miss + 8'd1;
                            end else begin
                                nack_last <= 1'b0; commit_start <= 1'b1; n_lat <= n_cnt; ok_now = 1'b1;
                            end
                        end
                    end
                end
                ST_IDLE: if (sample_req && init_done) begin
                    sample_req <= 1'b0; script <= 1'b1; pc <= 6'd0; rxi <= 4'd0; nack_run <= 1'b0;
                    ts_lat <= now_us; st <= ST_ISSUE;
                end
                default: st <= ST_PWR;
            endcase
            if (period_boundary) sample_req <= 1'b1;
            if (ok_now) n_cnt <= period_boundary ? 4'd1 : 4'd0;
            else if (period_boundary) n_cnt <= (n_cnt == 4'd15) ? 4'd15 : n_cnt + 4'd1;
        end
    end

    // ------------------------------------------------------------------ calibration, yaw integration, commit
    wire signed [15:0] gz_s = {rx[12], rx[13]};
    wire [2:0]  raw_sel = cfg_word[14:12];

    reg         calib_d;
    reg         calibrating, calibrated, int_en, auto_done, auto_pulse;
    reg [15:0]  cal_cnt;
    reg signed [31:0] cal_sum;
    reg signed [15:0] bias;
    reg signed [16:0] gz_c;
    reg signed [43:0] prod;
    reg signed [48:0] prod_n;
    reg signed [63:0] acc;
    reg [3:0]   vp;
    reg [15:0]  seq;
    reg [31:0]  yaw_out, ts_out;
    reg [15:0]  r_ax, r_ay, r_az, r_tmp, r_gx, r_gy, r_gz;

    wire signed [63:0] acc_n = int_en ? (acc + prod_n) : acc;
    wire cal_start = (cfg_word[16] & ~calib_d) | auto_pulse;

    always @(posedge clk) begin
        if (!rst_n) begin
            calib_d <= 1'b0; calibrating <= 1'b0; calibrated <= 1'b0; int_en <= 1'b0;
            auto_done <= 1'b0; auto_pulse <= 1'b0; cal_cnt <= 16'd0; cal_sum <= 32'sd0;
            bias <= 16'sd0; gz_c <= 17'sd0; prod <= 44'sd0; prod_n <= 49'sd0; acc <= 64'sd0;
            vp <= 4'd0; seq <= 16'd0; yaw_out <= 32'd0; ts_out <= 32'd0;
            r_ax <= 16'd0; r_ay <= 16'd0; r_az <= 16'd0; r_tmp <= 16'd0;
            r_gx <= 16'd0; r_gy <= 16'd0; r_gz <= 16'd0;
        end else begin
            calib_d    <= cfg_word[16];
            auto_pulse <= 1'b0;
            vp         <= {vp[2:0], commit_start};
            if (commit_start) int_en <= calibrated && !calibrating;

            // stage 1 (t1): calibration accumulate / subtract bias
            if (vp[0]) begin
                if (calibrating) begin
                    cal_sum <= cal_sum + gz_s;
                    cal_cnt <= cal_cnt + 16'd1;
                    if (cal_cnt == CAL_N - 1) begin
                        bias <= (cal_sum + gz_s) >>> CAL_SHIFT;
                        calibrating <= 1'b0; calibrated <= 1'b1; acc <= 64'sd0;
                    end
                end
                gz_c <= gz_s - bias;
            end
            // stage 2 (t2): multiply by per-sample constant
            if (vp[1]) prod <= gz_c * $signed({1'b0, K_C});
            // stage 3 (t3): multiply by number of elapsed sample periods (handles missed polls)
            if (vp[2]) prod_n <= prod * $signed({1'b0, n_lat});
            // stage 4 (t4): accumulate and commit everything at once
            if (vp[3]) begin
                acc     <= acc_n;
                yaw_out <= acc_n[61:30];
                ts_out  <= ts_lat;
                r_ax <= {rx[0],  rx[1]};  r_ay <= {rx[2],  rx[3]};  r_az <= {rx[4],  rx[5]};
                r_tmp <= {rx[6], rx[7]};  r_gx <= {rx[8],  rx[9]};  r_gy <= {rx[10], rx[11]};
                r_gz <= {rx[12], rx[13]};
                seq <= seq + 16'd1;
                if (!auto_done && seq == AUTO_CAL_AT) begin auto_done <= 1'b1; auto_pulse <= 1'b1; end
            end
            // calibration start request overrides (last assignment wins)
            if (cal_start) begin
                calibrating <= 1'b1; calibrated <= 1'b0; cal_cnt <= 16'd0; cal_sum <= 32'sd0;
            end
        end
    end

    // ------------------------------------------------------------------ outputs
    assign ts_word   = ts_out;
    assign now_word  = now_us;
    assign yaw_word  = yaw_out;
    assign stat_word = {seq, miss, 3'b000, nack_last, calibrated, calibrating, who_ok, init_done};
    assign raw_word  = (raw_sel == 3'd0) ? {r_ax, r_ay} :
                       (raw_sel == 3'd1) ? {r_az, r_tmp} :
                       (raw_sel == 3'd2) ? {r_gx, r_gy} :
                       (raw_sel == 3'd3) ? {r_gz, bias}  :
                       (raw_sel == 3'd5) ? {attempts, nack_cnt, 2'b00, nack_pc, st, script, pc[4:0]} :
                       (raw_sel == 3'd6) ? {30'd0, sda_in, scl_sync[1]} : {24'd0, who};
endmodule
