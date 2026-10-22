# Python / test_reader.py / Python 3.12 / projection and transform invariants
import math
import struct
import unittest
from reader import Memory, project
from discovery import profiles_from_text

class BufferMemory(Memory):
    def __init__(self):self.buffer=bytearray(8192)
    def read(self,a,n):return bytes(self.buffer[a:a+n])
    def put(self,a,fmt,*v):struct.pack_into(fmt,self.buffer,a,*v)

class GeometryTests(unittest.TestCase):
    def test_instance_ports_and_names(self):
        text='bst.instance.Nougat32.adb_port="5555"\nbst.instance.Nougat32.display_name="Meu Android"\nbst.instance.Bad.adb_port="99999"\nbst.instance.Bad2.adb_port="text"\n'
        self.assertEqual(profiles_from_text(text),{'127.0.0.1:5555':'Meu Android'})
    def test_projection_center_and_axis(self):
        m=(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)
        self.assertEqual(project((0,0,0),m,800,600),(400,300))
        self.assertEqual(project((1,1,0),m,800,600),(800,0))

    def test_behind_camera(self):
        m=(1,0,0,0,0,1,0,0,0,0,1,1,0,0,0,0)
        self.assertIsNone(project((0,0,-1),m,800,600))

    def hierarchy(self):
        m=BufferMemory();m.put(0x108,'<I',0x200)
        m.put(0x220,'<II',0x300,1);m.put(0x318,'<II',0x400,0x800)
        m.put(0x400,'<12f',10,0,0,0,0,0,math.sqrt(.5),math.sqrt(.5),2,2,2,0)
        m.put(0x430,'<12f',1,0,0,0,0,0,0,1,1,1,1,0)
        m.put(0x800,'<ii',-1,0)
        return m

    def test_rotated_scaled_parent(self):
        p=self.hierarchy().position(0x100)
        for actual,expected in zip(p,(10,2,0)):self.assertAlmostEqual(actual,expected,places=5)

    def test_cycle_rejected(self):
        m=self.hierarchy();m.put(0x800,'<ii',1,0)
        with self.assertRaises(ValueError):m.position(0x100)

if __name__=='__main__':unittest.main()
