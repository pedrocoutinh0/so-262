/**
 * This creates the buffer and the producer and consumer threads.
 *
 * @author Gagne, Galvin, Silberschatz
 * Operating System Concepts with Java - Sixth Edition
 * Copyright John Wiley & Sons - 2003.
 */
public class Factory
{
	public static void main(String args[]) {
		Buffer server = new BoundedBuffer();
        
            System.out.println("Aluno: Pedro Lucas Coutinho de Araujo");
      		// now create the producer and consumer threads
      		Thread producerThread = new Thread(new Producer(server));
      		Thread consumerThread = new Thread(new Consumer(server));
      
      		producerThread.start();
      		consumerThread.start();               
	}
}