from pathlib import Path
import lzma,struct,json,hashlib
src=Path('/home/cooper/Downloads/Win_Ulanzi_Studio_V3.4.8.20261027.exe');b=src.read_bytes();out=Path('/tmp/vibekey-update-20261104');o=0x23024;rows=[]
while o+8<len(b):
 n=struct.unpack_from('<Q',b,o)[0];s=n&((1<<63)-1)
 if not s or s>len(b)-o-8:break
 d=b[o+8:o+8+s]
 if n>>63:
  p=d[0];f={'id':lzma.FILTER_LZMA1,'dict_size':int.from_bytes(d[1:5],'little'),'lc':p%9,'lp':p//9%5,'pb':p//45}
  d=lzma.LZMADecompressor(format=lzma.FORMAT_RAW,filters=[f]).decompress(d[5:])
 name='block-%03d'%len(rows);(out/name).write_bytes(d);rows.append({'file':name,'offset':o,'size':len(d),'packed':s,'sha256':hashlib.sha256(d).hexdigest()});o+=8+s
(out/'manifest.json').write_text(json.dumps({'source_sha256':hashlib.sha256(b).hexdigest(),'blocks':rows,'end_offset':o},indent=2));print(len(rows),'blocks',sum(r['size'] for r in rows),'bytes')
