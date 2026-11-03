package com.wiiz.app;
import java.util.*;
public class ControllerLayoutTest {
 private static void check(int w,int h,float density){
  ControllerLayout l=new ControllerLayout(w,h,density);
  List<int[]> regions=new ArrayList<>();regions.add(l.screen);regions.addAll(l.buttons.values());
  for(int[] b:regions)if(b[0]<0||b[1]<0||b[2]<=0||b[3]<=0||b[0]+b[2]>w+1||b[1]+b[3]>h+1)throw new AssertionError("outside safe area "+w+"x"+h+" "+Arrays.toString(b));
  for(int i=0;i<regions.size();i++)for(int j=i+1;j<regions.size();j++){
   int[] a=regions.get(i),b=regions.get(j);
   int overlapW=Math.min(a[0]+a[2],b[0]+b[2])-Math.max(a[0],b[0]);
   int overlapH=Math.min(a[1]+a[3],b[1]+b[3])-Math.max(a[1],b[1]);
   if(overlapW>1&&overlapH>1)throw new AssertionError("overlap "+w+"x"+h+" "+i+" "+j);
  }
  if(l.buttons.size()!=14)throw new AssertionError("missing button");
 }
 public static void main(String[]args){for(int[] s:new int[][]{{1080,2200},{2200,900},{912,1840},{1840,800},{320,480},{640,320},{800,1200},{1200,800}}){float density=s[0]>1500||s[1]>1800?2.5f:1f;check(s[0],s[1],density);}System.out.println("CONTROLLER_LAYOUT_OK portrait/landscape/small/tablet safe_bounds=OK overlap=none all_buttons=14");}
}
