package com.wiiz.app;
import java.util.*;
import java.util.concurrent.*;
import java.io.IOException;
public class SaveQueueTest {
 public static void main(String[] args)throws Exception {
  CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
  List<Integer> written=Collections.synchronizedList(new ArrayList<>());
  try(SaveQueue queue=new SaveQueue((path,bytes)->{entered.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("timeout");written.add((int)bytes[0]);},message->{})){
   byte[] first={1};queue.write("Save/game.sav",first);first[0]=99;
   if(!entered.await(2,TimeUnit.SECONDS))throw new AssertionError("writer did not start");
   ExecutorService caller=Executors.newSingleThreadExecutor();
   try{caller.submit(()->{try{queue.write("Save/game.sav",new byte[]{2});queue.write("Save/game.sav",new byte[]{3});}catch(Exception e){throw new RuntimeException(e);}}).get(1,TimeUnit.SECONDS);}finally{caller.shutdown();release.countDown();}
   queue.flush();if(!written.equals(Arrays.asList(1,3)))throw new AssertionError("snapshot/coalescing/order: "+written);
  }
  try(SaveQueue queue=new SaveQueue((path,bytes)->{throw new IOException("permission lost");},message->{})){
   queue.write("state/slot1.json",new byte[]{4});
   boolean failed=false;try{queue.flush();}catch(IOException expected){failed=true;}
   if(!failed||queue.failure()==null)throw new AssertionError("failed write was hidden");
   try{queue.write("Save/game.sav",new byte[]{5});throw new AssertionError("write accepted after failure");}catch(IOException expected){}
  }
  System.out.println("SAVE_QUEUE_OK slow_IO=nonblocking snapshot=immutable latest=coalesced flush=ordered failure=reported");
 }
}
