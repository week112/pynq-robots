# generates the ROM case-table text for imu_reader.v
def line(pc, last, op, arg):
    return f"                6'd{pc}: rom = {{1'b{last}, {op}, {arg}}};"
init_regs = [("8'h6B","8'h01"),("8'h1A","DLPF_CFG"),("8'h19","8'h00"),("8'h1B","8'h00"),("8'h1C","8'h00")]
out=[]
out.append("        if (!script) begin")
out.append("            case (pc)")
pc=0
for r,v in init_regs:
    out.append(line(pc,0,"OP_START","8'h00")); pc+=1
    out.append(line(pc,0,"OP_WR","DEV_ADDR, 1'b0")); pc+=1
    out.append(line(pc,0,"OP_WR",r)); pc+=1
    out.append(line(pc,0,"OP_WR",v)); pc+=1
    out.append(line(pc,0,"OP_STOP","8'h00")); pc+=1
# WHO_AM_I
out.append(line(pc,0,"OP_START","8'h00")); pc+=1
out.append(line(pc,0,"OP_WR","DEV_ADDR, 1'b0")); pc+=1
out.append(line(pc,0,"OP_WR","8'h75")); pc+=1
out.append(line(pc,0,"OP_START","8'h00")); pc+=1
out.append(line(pc,0,"OP_WR","DEV_ADDR, 1'b1")); pc+=1
out.append(line(pc,0,"OP_RDN","8'h00")); pc+=1
out.append(line(pc,1,"OP_STOP","8'h00")); pc+=1
out.append("                default: rom = {1'b1, OP_STOP, 8'h00};")
out.append("            endcase")
out.append("        end else begin")
out.append("            case (pc)")
pc=0
out.append(line(pc,0,"OP_START","8'h00")); pc+=1
out.append(line(pc,0,"OP_WR","DEV_ADDR, 1'b0")); pc+=1
out.append(line(pc,0,"OP_WR","8'h3B")); pc+=1
out.append(line(pc,0,"OP_START","8'h00")); pc+=1
out.append(line(pc,0,"OP_WR","DEV_ADDR, 1'b1")); pc+=1
for i in range(13):
    out.append(line(pc,0,"OP_RDA","8'h00")); pc+=1
out.append(line(pc,0,"OP_RDN","8'h00")); pc+=1
out.append(line(pc,1,"OP_STOP","8'h00")); pc+=1
out.append("                default: rom = {1'b1, OP_STOP, 8'h00};")
out.append("            endcase")
out.append("        end")
open("rom_cases.txt","w").write("\n".join(out)+"\n")
print("\n".join(out))
