from Trafficnet import Trafficnet
from Linkmodel import *
import matplotlib.pyplot as plt
import math 
import random

#分配函数
def random_partition(m, n):
    # Split the shuffled items into n parts
    distribution = []
    current_sum = 0
    for i in range(n):
        if i < n - 1:
            # Randomly decide the size of the current part
            part_size = random.randint(0, m - current_sum)
            distribution.append(part_size)
            current_sum += part_size
        else:
            # The last part gets the remaining quantity
            distribution.append(m - current_sum)
    
    return distribution
    # if n <= 0:
    #     raise ValueError("Number of partitions (n) must be greater than zero.")   
    # # 随机生成n-1个划分点
    # partitions = sorted(random.sample(range(m), n-1))
    # partitions = [0] + partitions + [m]   
    # # 计算划分后的部分
    # partitions_values = [partitions[i+1] - partitions[i] for i in range(n)]    
    # return partitions_values
    

class TranfficSolution:
    def __init__(self) -> None:
        self.Tperiod=20
        self.Tnet=Trafficnet(self.Tperiod,4)  #交通网络
        self.Tnet.Trafficnet_readcsv()  #加载网络数据

        self.racePool=[]    #种群池
        self.Pc_cross=0.8    #交叉概率
        self.Pm_mutation=0.4    #变异概率
        self.iterationNum=20    #迭代次数
        self.raceSize=5    #种群数量
        self.geneLength=0   #基因长度

        self.iterateRecord=[]   #记录每一代最好的成绩
        self.bestEntity={}  #最终优化结果

    #生成初始分配方案   初始化种群
    def TS_GenerateInitialSolution(self):
        #生成种群数量个初始方案
        for i in range(self.raceSize):
            #初始化需求方案
            DG_apt={}
            for ar in self.Tnet.AR_sourcelinkSet:
                for t in range(1,self.Tnet.TotalTimePeriod):
                    for p in self.Tnet.A_linkSet[ar].PathSet:
                        if self.Tnet.PathSet[p].isUsed==1:
                            DG_apt.update({(ar,p,t):0})
            #随机路径选择
            for ar in self.Tnet.AR_sourcelinkSet:
                tepLink=self.Tnet.A_linkSet[ar]
                # print(id(tepLink),id(self.Tnet.A_linkSet[ar]))
                for t in range(1,self.Tnet.TotalTimePeriod):
                    #油车路径分配
                    for od in tepLink.DG_Demand[t].keys():
                        pathNum=len(self.Tnet.PathSetByOdforGv[od])
                        dnum=tepLink.DG_Demand[t][od]
                        solution=[0]*pathNum
                        if(dnum>0):
                            solution=random_partition(dnum,pathNum)
                            # print(solution)
                        #根据分配数给DG赋值
                        for i in range(pathNum):
                            DG_apt[ar,self.Tnet.PathSetByOdforGv[od][i],t]+=solution[i]
                    #电车路径分配
                    for odel in tepLink.DE_Demand[t]:
                        pathNum=len(self.Tnet.PathSetByOdElforEv[odel])
                        dnum=tepLink.DE_Demand[t][odel]
                        solution=[0]*pathNum
                        if(dnum>0):
                            solution=random_partition(dnum,pathNum)
                        #根据分配数给DG赋值
                        for i in range(pathNum):
                            DG_apt[ar,self.Tnet.PathSetByOdElforEv[odel][i],t]+=solution[i]
            #将获得的方案添加到基因池
            self.racePool.append(DG_apt.copy())
        ##
        # self.geneLength=len(self.racePool[0])
        # self.Tnet.Trafficnet_loadSolution(self.racePool[0])
        # print("初始的种群基因池为:\nThe initial Solution is :\n",self.racePool)


    #交叉
    def TS_Intersect(self,parent1,parent2):
        start=0
        end=self.Tnet.lastDemandTime
        #寻找合适的基因段交叉 这里长度不超过整个基因的0.3倍
        while (end-start)>0.4*self.Tnet.lastDemandTime:
            pieces=random.sample(range(1,self.Tnet.lastDemandTime),2)
            start=min(pieces)
            end=max(pieces)
        #选择一个OD对开始交叉
        odId=random.sample(self.Tnet.ODset,1)[0]
        linkId=odId[0]
        for t in range(start,end):
            for p in self.Tnet.PathSetByOD[odId]:
                # print("\n亲本一交叉前:({},{},{}):{}".format(linkId,p,t,parent1[linkId,p,t]))
                # print("亲本二交叉前:({},{},{}):{}".format(linkId,p,t,parent2[linkId,p,t]))
                tep=parent1[linkId,p,t]
                parent1[linkId,p,t]=parent2[linkId,p,t]
                parent2[linkId,p,t]=tep
                # print("亲本一交叉后:({},{},{}):{}".format(linkId,p,t,parent1[linkId,p,t]))
                # print("亲本二交叉后:({},{},{}):{}".format(linkId,p,t,parent2[linkId,p,t]))

    #变异
    def TS_Mutation(self,parent):
        #随机选择一个时间和节点的OD需求重新分配
        linkId=random.sample(self.Tnet.AR_sourcelinkSet,1)[0]
        t=random.randint(1,self.Tnet.lastDemandTime)
        #油车重新分配
        demand=self.Tnet.A_linkSet[linkId].DG_Demand[t]
        odId=random.sample(list(demand.keys()),1)[0]
        #重新分配
        pathNum=len(self.Tnet.PathSetByOdforGv[odId])
        dnum=self.Tnet.A_linkSet[linkId].DG_Demand[t][odId]
        solution=[0]*pathNum
        if(dnum>0):
            solution=random_partition(dnum,pathNum)
            #根据分配数给DG赋值
            for i in range(pathNum):
            #    print("\n个体变异前分配方案({},{},{}):{}".format(linkId,self.Tnet.PathSetByOD[odId][i],t,parent[linkId,self.Tnet.PathSetByOD[odId][i],t]))
               parent[linkId,self.Tnet.PathSetByOdforGv[odId][i],t] = solution[i]
            #    print("个体变异后分配方案({},{},{}):{}".format(linkId,self.Tnet.PathSetByOD[odId][i],t,parent[linkId,self.Tnet.PathSetByOD[odId][i],t]))

    #第二中变异方式 第一中貌似挺麻烦
    def TS_Mutation02(self,parent):
        pass

    #竞标赛选取下一轮种群
    def TS_tournament(self,times):
        #先计算适应性指标
        fitness={}
        poolLen=len(self.racePool)
        for i in range(poolLen):
            self.Tnet.Trafficnet_init_U_V()
            self.Tnet.Trafficnet_loadSolution(self.racePool[i])
            self.Tnet.Trafficnet_Run()
            self.Tnet.Trafficnet_getResult()
            # fitness.update({i:self.Tnet.SystemTravalTime+100*self.Tnet.SystemVariance})   #这个是考虑通行时间方差的适应度
            fitness.update({i:self.Tnet.SystemTravalTime})     #这个是选择最短通行时间的适应度 不如用LP解决
            print("第{}个种群个体在第{}次迭代的数据:\n通行时间 {},时间方差 {}\n".format(i,times,self.Tnet.SystemTravalTime,\
                                                                  self.Tnet.SystemVariance))
        #选择适应度高的个体
        newPool=[]
        raceList=[i for i in range(len(self.racePool))]
        raceList=sorted(raceList,key=lambda i:fitness[i])
            #记录一下当代适应性最好的个体
        self.iterateRecord.append(fitness[raceList[0]])
        for i in range(self.raceSize):
            newPool.append(self.racePool[raceList[i]])
        self.racePool=newPool

    #生成下一代种群
    def TS_GenerateNextSolution(self):
        #种群进行一轮迭代
        for i in range(int(self.raceSize/2)):
        #随机选取两个个体交叉    
            parent=random.sample(self.racePool,2)
            percent=random.random()
            parent1=parent[0].copy()
            parent2=parent[1].copy()
            if percent<self.Pc_cross:
                self.TS_Intersect(parent1,parent2)        
        #随机进行变异
            if percent<self.Pm_mutation:
                self.TS_Mutation(parent1)
                self.TS_Mutation(parent2)
        
        #将子代添加到种群池
            self.racePool.append(parent1)
            self.racePool.append(parent2)
        
    #获取结果
    def TS_GetResult(self):
        #给出迭代数据   
        print("种群迭代最优记录为:{}".format(self.iterateRecord))
        x=[i for i in range(self.iterationNum)]
        plt.plot(x,self.iterateRecord)
        plt.xlabel(xlabel='Tteration Times')
        plt.ylabel(ylabel='Total cost')
        plt.show()
        #获取最优结果并输出信息
        self.bestEntity=self.racePool[0]
        self.Tnet.Trafficnet_init_U_V()
        self.Tnet.Trafficnet_loadSolution(self.bestEntity)
        self.Tnet.Trafficnet_Run()
        self.Tnet.Trafficnet_getResult()
        self.Tnet.Trafficnet_printInfo()


if __name__ == "__main__":
    #创建一个交通网络
    example=TranfficSolution()
    #生成初始种群
    example.TS_GenerateInitialSolution()
    for i in range(example.iterationNum):
        #遗传变异
        example.TS_GenerateNextSolution()
        #选择下一代基因
        example.TS_tournament(i)
    example.TS_GetResult()
    # example.Tnet.Trafficnet_Run()
    # example.Tnet.Trafficnet_printInfo()
    # example.Tnet.Trafficnet_getResult()
