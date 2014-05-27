#!/usr/bin/env python3

'''QQWry 模块，提供读取纯真IP数据库的数据的功能。

纯真数据库格式参考 http://lumaqq.linuxsir.org/article/qqwry_format_detail.html
作者 AutumnCat. 最后修改在 2008年 04月 29日
bones7456 最后修改于 2009-02-02
lilydjwg 修改于 2014-05-26
本程序遵循 GNU GENERAL PUBLIC LICENSE Version 2 (http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt)
'''

#数据文件下载地址： http://update.cz88.net/soft/qqwry.rar

from struct import unpack, pack
import sys, _socket, mmap
from collections import namedtuple

DataFileName = "/home/lilydjwg/etc/data/QQWry.Dat"

def _ip2ulong(ip):
  '''点分十进制 -> unsigned long
  '''
  return unpack('>L', _socket.inet_aton(ip))[0]

def _ulong2ip(ip):
  '''unsigned long -> 点分十进制
  '''
  return _socket.inet_ntoa(pack('>L', ip))

class ipInfo(namedtuple('ipInfo', 'sip eip country area')):
  __slots__ = ()
  def __str__(self):
    '''str(x)
    '''
    # TODO: better formatting
    return str(self[0]).ljust(16) + ' - ' + str(self[1]).rjust(16) + ' ' + self[2] + self[3]

  def normalize(self):
    '''转化ip地址成点分十进制.
    '''
    return self.__class__(
      _ulong2ip(self[0]), _ulong2ip(self[1]), self[2], self[3])

class QQWry:
  def __init__(self, dbfile = DataFileName, charset = 'gbk'):
    if isinstance(dbfile, (str, bytes)):
      dbfile = open(dbfile, 'rb')

    self.f = dbfile
    self.charset = charset
    self.f.seek(0)
    self.indexBaseOffset = unpack('<L', self.f.read(4))[0] #索引区基址
    self.Count = (unpack('<L', self.f.read(4))[0] - self.indexBaseOffset) // 7 # 索引数-1

  def Lookup(self, ip):
    '''x.Lookup(ip) -> (sip, eip, country, area) 查找 ip 所对应的位置.

    ip, sip, eip 是点分十进制记录的 ip 字符串.
    sip, eip 分别是 ip 所在 ip 段的起始 ip 与结束 ip.
    '''
    return self.nLookup(_ip2ulong(ip))

  def nLookup(self, ip):
    '''x.nLookup(ip) -> (sip, eip, country, area) 查找 ip 所对应的位置.

    ip 是 unsigned long 型 ip 地址.
    其它同 x.Lookup(ip).
    '''
    si = 0
    ei = self.Count
    if ip < self._readIndex(si)[0]:
      raise LookupError('IP NOT Found.')
    elif ip >= self._readIndex(ei)[0]:
      si = ei
    else: # keep si <= ip < ei
      while (si + 1) < ei:
        mi = (si + ei) // 2
        if self._readIndex(mi)[0] <= ip:
          si = mi
        else:
          ei = mi
    ipinfo = self[si]
    if ip > ipinfo[1]:
      raise LookupError('IP NOT Found.')
    else:
      return ipinfo

  def __str__(self):
    tmp = []
    tmp.append('RecCount:')
    tmp.append(str(len(self)))
    tmp.append('\nVersion:')
    tmp.extend(self[self.Count].normalize()[2:])
    return ''.join(tmp)

  def __len__(self):
    '''len(x)
    '''
    return self.Count + 1

  def __getitem__(self, key):
    '''x[key]

    若 key 为整数, 则返回第key条记录(从0算起, 注意与 x.nLookup(ip) 不一样).
    若 key 为点分十进制的 ip 描述串, 同 x.Lookup(key).
    '''
    if isinstance(key, int):
      if key >=0 and key <= self.Count:
        index = self._readIndex(key)
        sip = index[0]
        self.f.seek(index[1])
        eip = unpack('<L', self.f.read(4))[0]
        country, area = self._readRec()
        if area == ' CZ88.NET':
          area = ''
        return ipInfo(sip, eip, country, area)
      else:
        raise KeyError('INDEX OUT OF RANGE.')
    elif isinstance(key, str):
      return self.Lookup(key).normalize()
    else:
      raise TypeError('WRONG KEY TYPE.')

  def _read3ByteOffset(self):
    '''_read3ByteOffset() -> unsigned long 从文件 f 读入长度为3字节的偏移.
    '''
    return unpack('<L', self.f.read(3) + b'\x00')[0]

  def _readCStr(self):
    if self.f.tell() == 0:
      return 'Unknown'

    return self._read_cstring().decode(self.charset, errors='replace')

  def _read_cstring(self):
    tmp = []
    ch = self.f.read(1)
    while ch != b'\x00':
      tmp.append(ch)
      ch = self.f.read(1)
    return b''.join(tmp)

  def _readIndex(self, n):
    '''x._readIndex(n) -> (ip ,offset) 读取第n条索引.
    '''
    self.f.seek(self.indexBaseOffset + 7 * n)
    return unpack('<LL', self.f.read(7) + b'\x00')

  def _readRec(self, onlyOne=False):
    '''x._readRec() -> (country, area) 读取记录的信息.
    '''
    mode = unpack('B', self.f.read(1))[0]
    if mode == 0x01:
      rp = self._read3ByteOffset()
      bp = self.f.tell()
      self.f.seek(rp)
      result = self._readRec(onlyOne)
      self.f.seek(bp)
    elif mode == 0x02:
      rp = self._read3ByteOffset()
      bp = self.f.tell()
      self.f.seek(rp)
      result = self._readRec(True)
      self.f.seek(bp)
      if not onlyOne:
        result.append(self._readRec(True)[0])
    else: # string
      self.f.seek(-1,1)
      result = [self._readCStr()]
      if not onlyOne:
        result.append(self._readRec(True)[0])

    return result

class MQQWry(QQWry):
  '''
  将数据库放到内存
  查询速度大约快两倍.

  In [6]: %timeit t(QQWry())
  100 loops, best of 3: 4.09 ms per loop

  In [7]: %timeit t(MQQWry())
  100 loops, best of 3: 2.22 ms per loop
  '''
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.f = mmap.mmap(self.f.fileno(), 0, access = 1)

  def _read_cstring(self):
    start = self.f.tell()
    end = self.f.find(b'\x00')
    if end < 0:
      raise Exception('fail to read C string')
    self.f.seek(end + 1)
    return self.f[start:end]

if __name__ == '__main__':
  Q = QQWry()
  if len(sys.argv) == 1:
    print(Q)
  elif len(sys.argv) == 2:
    if sys.argv[1] == '-': #参数只有一个“-”时，从标准输入读取IP
      print(''.join(Q[input()][2:]))
    elif sys.argv[1] in ('all', '-a', '-all'): #遍历示例代码
      try:
        for i in Q:
          print(i.normalize())
      except IOError:
        pass
    else: #参数只有一个IP时，只输出简要的信息
      print(''.join(Q[sys.argv[1]][2:]))
  else:
    for i in sys.argv[1:]:
      print(Q[i])
