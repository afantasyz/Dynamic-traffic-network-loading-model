from Trafficnet import Trafficnet
from Linkmodel import *
import matplotlib.pyplot as plt
import math 
import random

#分配函数
def random_partition(m, n):
    if n <= 0:
        raise ValueError("Number of partitions (n) must be greater than zero.")   
    # 随机生成n-1个划分点
    partitions = sorted(random.sample(range(m), n-1))
    partitions = [0] + partitions + [m]   
    # 计算划分后的部分
    partitions_values = [partitions[i+1] - partitions[i] for i in range(n)]    
    return partitions_values

class TranfficSolution:
    def __init__(self) -> None:
        self.Tperiod=20
        self.Tnet=Trafficnet(self.Tperiod,1)  #交通网络
        self.Tnet.Trafficnet_readcsv()  #加载网络数据

        self.racePool=[]    #种群池
        self.Pc_cross=0.8    #交叉概率
        self.Pm_mutation=0.4    #变异概率
        self.iterationNum=20    #迭代次数
        self.raceSize=5    #种群数量
        self.geneLength=0   #基因长度

        self.iterateRecord=[]   #记录每一代最好的成绩
        self.bestEntity={}  #最终优化结果


    #网络更新   可删除，此部分已封装到Trafficnet.py文件下
    def Trafficnet_update(self,t):
        #起始link更新
        for i in self.Tnet.AR_sourcelinkSet:
            tepLink=self.Tnet.A_linkSet[i]
            for p in tepLink.PathSet:
                tepu=self.Tnet.DG_apt[i,p,t]
                tepLink.uv.URecord[p,t]=tepu
                tepLink.uv.UsumRecord[t]+=tepu

        #一般link更新
        for n in self.Tnet.GN_generalNode:           
            #用到的基本数据
            inLink=self.Tnet.N_nodeSet[n].inLink
            outLink=self.Tnet.N_nodeSet[n].outLink
            Si={}   #发出流Si
            Rj={}   #接收流Rj
            Sij={}  #从编号i到j的发出流
            Rij={}  #从编号i到j的接收流
            Gij={}  #从编号i到j的实际流量
            #每个link中各种车流按路径分布的比例
            flowbyPath={}
            flowbyNext={}
            for i in inLink:
                flowbyPath.update({i:{}})
                for j in outLink:
                    Sij.update({(i,j):0})
                    Rij.update({(i,j):0})
                    Gij.update({(i,j):0})
                    flowbyNext.update({(i,j):0})
            
            #当前累计流赋值一下
            for i in inLink:
                self.Tnet.A_linkSet[i].uv.VsumRecord[t]=self.Tnet.A_linkSet[i].uv.VsumRecord[t-1]
            for j in outLink:
                self.Tnet.A_linkSet[j].uv.UsumRecord[t]=self.Tnet.A_linkSet[j].uv.UsumRecord[t-1]

           #更新Si的部分
            for i in inLink:
                tepLink=self.Tnet.A_linkSet[i]
                lastT=tepLink.vt_FreeFlowTime
                tepS=0
                if t-lastT>0:
                    tepS=tepLink.uv.UsumRecord[t-lastT]-tepLink.uv.VsumRecord[t-1]
                    Si.update({i:min(tepLink.Of_outflowCapacity[0],tepS)})
                else:
                    Si.update({i:0})
                #更新Sij部分
                for p in tepLink.PathSet:
                    path=self.Tnet.PathSet[p]
                    aindex=path[path.index(i)+1]
                    if t-lastT>0 and tepS>0:
                        per=(tepLink.uv.URecord[p,t-lastT]-tepLink.uv.VRecord[p,t-1]) /tepS
                        flowbyPath[i].update({p:per})
                        flowbyNext[i,aindex]+=per
                        Sij[i,aindex]+=Si[i]*per 
                    else:
                        flowbyPath[i].update({p:0})

            #更新Rj部分
            tepPer=[]
            for j in outLink:
                tepLink=self.Tnet.A_linkSet[j]
                lastT=tepLink.wt_BackwardTime
                if t-lastT>0:
                    Rj.update({j:min(tepLink.If_inflowCapacity[0],tepLink.uv.VsumRecord[t-lastT]+tepLink.q_MaxFlow-tepLink.uv.UsumRecord[t-1])})
                else:
                    Rj.update({j:tepLink.If_inflowCapacity[0]})
                #此处计算FIFO约束
                sumSij=0
                for i in inLink:
                    sumSij+=Sij[(i,j)]
                if sumSij==0:
                    sumSij=1
                tepPer.append(Rj[j]/sumSij)
                
            #更新Rij部分和Gij
            for i in inLink:
                for j in outLink:
                    Rij[(i,j)]=min(tepPer)*Sij[(i,j)]
                    Gij[(i,j)]=min(Rij[(i,j)],Sij[(i,j)])
                    print("The flow from {} to {} is {}".format(i,j,Gij[(i,j)]))
                    self.Tnet.A_linkSet[i].uv.VsumRecord[t]+=Gij[(i,j)]
                    self.Tnet.A_linkSet[j].uv.UsumRecord[t]+=Gij[(i,j)]

            #将Gij的数值更新u和v
            for i in inLink:
                tepLink=self.Tnet.A_linkSet[i]
                for p in tepLink.PathSet:
                    path=self.Tnet.PathSet[p]
                    aindex=path[path.index(i)+1]
                    tepNum=tepLink.uv.VRecord[p,t-1]
                    if flowbyNext[(i,aindex)]>0:
                        tepNum+=Gij[(i,aindex)]*(flowbyPath[i][p]/flowbyNext[(i,aindex)])
                    tepLink.uv.VRecord[p,t]=tepNum
                    self.Tnet.A_linkSet[aindex].uv.URecord[p,t]=tepNum


    #生成初始分配方案   初始化种群
    def TS_GenerateInitialSolution(self):
        #生成种群数量个初始方案
        for i in range(self.raceSize):
            #随机路径选择
            DG_apt={}
            for ar in self.Tnet.AR_sourcelinkSet:
                tepLink=self.Tnet.A_linkSet[ar]
                # print(id(tepLink),id(self.Tnet.A_linkSet[ar]))
                for t in range(1,self.Tnet.TotalTimePeriod):
                    for od in tepLink.DG_Demand[t].keys():
                        pathNum=len(self.Tnet.PathSetByOD[od])
                        dnum=tepLink.DG_Demand[t][od]
                        solution=[0]*pathNum
                        if(dnum>0):
                            solution=random_partition(tepLink.DG_Demand[t][od],pathNum)
                            # print(solution)
                        #根据分配数给DG赋值
                        for i in range(pathNum):
                            DG_apt.update({(ar,self.Tnet.PathSetByOD[od][i],t):solution[i]})
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
        demand=self.Tnet.A_linkSet[linkId].DG_Demand[t]
        odId=random.sample(list(demand.keys()),1)[0]
        #重新分配
        pathNum=len(self.Tnet.PathSetByOD[odId])
        dnum=self.Tnet.A_linkSet[linkId].DG_Demand[t][odId]
        solution=[0]*pathNum
        if(dnum>0):
            solution=random_partition(dnum,pathNum)
            #根据分配数给DG赋值
            for i in range(pathNum):
            #    print("\n个体变异前分配方案({},{},{}):{}".format(linkId,self.Tnet.PathSetByOD[odId][i],t,parent[linkId,self.Tnet.PathSetByOD[odId][i],t]))
               parent[linkId,self.Tnet.PathSetByOD[odId][i],t] = solution[i]
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
    # # for i in range(1,example.Tnet.TotalTimePeriod):
    # #     example.Trafficnet_update(i)
    # example.Tnet.Trafficnet_printInfo()
    # example.Tnet.Trafficnet_getResult()
