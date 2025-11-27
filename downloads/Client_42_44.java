import java.io.*;
import java.net.*;
import java.util.*;

public class Client_42_44 {

    public static void main(String args[]) {
        try {
            Socket sck = new Socket("localhost", 1992);
            BufferedReader in = new BufferedReader(new InputStreamReader(sck.getInputStream()));
            PrintWriter out = new PrintWriter(sck.getOutputStream(), true);
            Scanner sc = new Scanner(System.in);

            System.out.println("Select TCP mode (TAHOE or RENO): ");
            String mode = sc.next().toUpperCase();

            System.out.println("Enter number of rounds: ");
            int N = sc.nextInt();
            out.println(N);

            int cwnd = 1;
            int ssthresh = 8;
            int nextPkt = 1;

            System.out.println("\n== TCP " + mode + " Mode ==");

            String lastACK = "";
            double estimatedRTT = 500; // initial RTT in ms
            double devRTT = 250;
            double timeoutInterval = estimatedRTT + 4 * devRTT;

            for (int round = 1; round <= N; round++) {
                System.out.println("\nRound " + round + ": cwnd=" + cwnd + ", ssthresh=" + ssthresh);

                List<String> packets = new ArrayList<>();
                int startPkt = nextPkt;

                for (int i = 0; i < cwnd; i++) {
                    packets.add("pkt" + nextPkt);
                    nextPkt++;
                }

                out.println(round);
                out.println(String.join(",", packets));
                System.out.println("Sent packets: " + String.join(",", packets));

                List<String> receivedAcks = new ArrayList<>();
                boolean timeoutOccurred = false;

                for (int i = 0; i < packets.size(); i++) {
                    long startTime = System.currentTimeMillis();
                    String ack = null;

                    
                    while ((System.currentTimeMillis() - startTime) < timeoutInterval) {
                        if (in.ready()) {
                            ack = in.readLine();
                            break;
                        }
                        Thread.sleep(10); 
                    }

                    if (ack == null) {
                        
                        timeoutOccurred = true;
                        System.out.println("==> Timeout occurred for packet: " + packets.get(i));
                        
                        nextPkt = startPkt + i;
                        cwnd = 1; 
                        ssthresh = cwnd / 2;
                        break;
                    } else if (ack.equals("END")) {
                        break;
                    } else {
                        receivedAcks.add(ack);

                        
                        long sampleRTT = System.currentTimeMillis() - startTime;
                        estimatedRTT = 0.875 * estimatedRTT + 0.125 * sampleRTT;
                        devRTT = 0.75 * devRTT + 0.25 * Math.abs(sampleRTT - estimatedRTT);
                        timeoutInterval = estimatedRTT + 4 * devRTT;

                        System.out.println("Received ACK: " + ack + " (SampleRTT=" + sampleRTT + "ms)");
                    }
                }

                
                if (!timeoutOccurred) {
                    if (cwnd < ssthresh) {
                        cwnd *= 2;
                        System.out.println("Slow Start: cwnd -> " + cwnd);
                    } else {
                        cwnd += 1;
                        System.out.println("Congestion Avoidance: cwnd -> " + cwnd);
                    }
                }
            }

            sck.close();
            System.out.println("\nClient disconnected.");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}